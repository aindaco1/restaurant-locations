#!/usr/bin/env node

import { pathToFileURL } from "node:url";

export const PRODUCTION_HOSTNAME = "healthcode.dustwave.xyz";
export const API_BASE_URL = "https://api.cloudflare.com/client/v4";

const HOST_EXPRESSION = `(http.host eq "${PRODUCTION_HOSTNAME}")`;
const VERSIONED_ASSET_PATH_EXPRESSION = [
  "(",
  'http.request.uri.path wildcard r"/assets/*.*.*" or ',
  'http.request.uri.path wildcard r"/favicon.*.svg" or ',
  '(http.request.uri.path eq "/data/violations_latest.json" and ',
  'http.request.uri.query contains "v=")',
  ")",
].join("");
const VERSIONED_ASSET_EXPRESSION =
  `(http.host eq "${PRODUCTION_HOSTNAME}" and ${VERSIONED_ASSET_PATH_EXPRESSION})`;
const IMMUTABLE_RESPONSE_EXPRESSION =
  `(http.host eq "${PRODUCTION_HOSTNAME}" and ${VERSIONED_ASSET_PATH_EXPRESSION} `
  + "and http.response.code eq 200)";

export const MANAGED_RULES = Object.freeze([
  {
    phase: "http_config_settings",
    rulesetName: "Zone-level Configuration Ruleset",
    rule: {
      ref: "healthcode_performance_safeguards",
      action: "set_config",
      action_parameters: {
        disable_rum: true,
        rocket_loader: false,
      },
      description: "Healthcode performance safeguards",
      enabled: true,
      expression: HOST_EXPRESSION,
    },
  },
  {
    phase: "http_request_cache_settings",
    rulesetName: "Zone-level Cache Ruleset",
    rule: {
      ref: "healthcode_immutable_assets",
      action: "set_cache_settings",
      action_parameters: {
        cache: true,
        browser_ttl: {
          default: 31536000,
          mode: "override_origin",
        },
        edge_ttl: {
          default: 31536000,
          mode: "override_origin",
        },
      },
      description: "Healthcode immutable versioned assets",
      enabled: true,
      expression: VERSIONED_ASSET_EXPRESSION,
    },
  },
  {
    phase: "http_response_cache_settings",
    rulesetName: "Zone-level Cache Response Ruleset",
    rule: {
      ref: "healthcode_immutable_asset_headers",
      action: "set_cache_control",
      action_parameters: {
        immutable: { operation: "set" },
        "max-age": { operation: "set", value: 31536000 },
        "s-maxage": {
          cloudflare_only: true,
          operation: "set",
          value: 31536000,
        },
      },
      description: "Healthcode immutable asset response headers",
      enabled: true,
      expression: IMMUTABLE_RESPONSE_EXPRESSION,
    },
  },
]);

function fail(message) {
  throw new Error(message);
}

function cloudflareError(payload, status) {
  const details = [
    ...(Array.isArray(payload?.errors) ? payload.errors : []),
    ...(Array.isArray(payload?.messages) ? payload.messages : []),
  ]
    .map((entry) => `${entry?.code || "error"}: ${entry?.message || "unknown"}`)
    .join("; ");
  return details || `HTTP ${status}`;
}

export async function cloudflareRequest({
  zoneId,
  apiToken,
  path,
  method = "GET",
  body,
  fetchImpl = globalThis.fetch,
  allowNotFound = false,
}) {
  const response = await fetchImpl(
    `${API_BASE_URL}/zones/${zoneId}${path}`,
    {
      method,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
  );
  const payload = await response.json().catch(() => ({}));

  if (allowNotFound && response.status === 404) return null;
  if (!response.ok || payload.success !== true) {
    fail(
      `Cloudflare ${method} ${path} failed (${response.status}): `
        + cloudflareError(payload, response.status),
    );
  }
  return payload.result;
}

function sortObject(value) {
  if (Array.isArray(value)) return value.map(sortObject);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.keys(value)
      .filter((key) => !(key === "cloudflare_only" && value[key] === false))
      .sort()
      .map((key) => [key, sortObject(value[key])]),
  );
}

function stableRule(rule) {
  // Rules created in the dashboard receive an immutable generated ref. Match
  // them by description and compare only the deployable behavior.
  return sortObject({
    action: rule?.action,
    action_parameters: rule?.action_parameters,
    description: rule?.description,
    enabled: rule?.enabled !== false,
    expression: rule?.expression,
  });
}

export function rulesMatch(actual, desired) {
  return JSON.stringify(stableRule(actual)) === JSON.stringify(stableRule(desired));
}

export function ruleUpdateBody(existing, desired) {
  const body = structuredClone(desired);
  if (existing?.ref !== desired?.ref) delete body.ref;
  return body;
}

export async function syncManagedRule({
  zoneId,
  apiToken,
  managedRule,
  checkOnly = false,
  fetchImpl = globalThis.fetch,
  logger = console,
}) {
  const { phase, rulesetName, rule } = managedRule;
  const request = (options) => cloudflareRequest({
    zoneId,
    apiToken,
    fetchImpl,
    ...options,
  });
  const phasePath = `/rulesets/phases/${phase}/entrypoint`;
  let ruleset = await request({ path: phasePath, allowNotFound: true });

  if (!ruleset) {
    if (checkOnly) fail(`Missing Cloudflare ${phase} ruleset.`);
    ruleset = await request({
      path: "/rulesets",
      method: "POST",
      body: {
        kind: "zone",
        name: rulesetName,
        phase,
        rules: [rule],
      },
    });
    logger.log(`Created ${rule.description}.`);
  } else {
    const matches = (ruleset.rules || []).filter(
      (candidate) => candidate.ref === rule.ref
        || candidate.description === rule.description,
    );
    if (matches.length > 1) {
      fail(`Found multiple Cloudflare rules for ${rule.description}.`);
    }

    const existing = matches[0];
    if (!existing) {
      if (checkOnly) fail(`Missing Cloudflare rule: ${rule.description}.`);
      await request({
        path: `/rulesets/${ruleset.id}/rules`,
        method: "POST",
        body: rule,
      });
      logger.log(`Created ${rule.description}.`);
    } else if (!rulesMatch(existing, rule)) {
      if (checkOnly) fail(`Cloudflare rule drift: ${rule.description}.`);
      await request({
        path: `/rulesets/${ruleset.id}/rules/${existing.id}`,
        method: "PATCH",
        body: ruleUpdateBody(existing, rule),
      });
      logger.log(`Updated ${rule.description}.`);
    } else {
      logger.log(`Unchanged ${rule.description}.`);
    }
  }

  const deployed = await request({ path: phasePath });
  const deployedMatches = (deployed.rules || []).filter(
    (candidate) => candidate.ref === rule.ref
      || candidate.description === rule.description,
  );
  if (deployedMatches.length !== 1 || !rulesMatch(deployedMatches[0], rule)) {
    fail(`Cloudflare verification failed: ${rule.description}.`);
  }
  return deployedMatches[0];
}

export async function syncCloudflareConfig({
  zoneId,
  apiToken,
  checkOnly = false,
  fetchImpl = globalThis.fetch,
  logger = console,
}) {
  if (!/^[a-f0-9]{32}$/i.test(String(zoneId || ""))) {
    fail("CLOUDFLARE_ZONE_ID is missing or invalid.");
  }
  if (!String(apiToken || "").trim()) {
    fail("CLOUDFLARE_API_TOKEN is required.");
  }

  for (const managedRule of MANAGED_RULES) {
    await syncManagedRule({
      zoneId,
      apiToken,
      managedRule,
      checkOnly,
      fetchImpl,
      logger,
    });
  }
}

async function run() {
  await syncCloudflareConfig({
    zoneId: process.env.CLOUDFLARE_ZONE_ID,
    apiToken: process.env.CLOUDFLARE_API_TOKEN,
    checkOnly: process.argv.includes("--check"),
  });
}

if (
  typeof process !== "undefined"
  && process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  run().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
