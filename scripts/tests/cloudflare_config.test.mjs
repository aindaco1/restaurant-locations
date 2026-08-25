import assert from "node:assert/strict";
import test from "node:test";

import {
  MANAGED_RULES,
  PRODUCTION_HOSTNAME,
  ruleUpdateBody,
  rulesMatch,
} from "../sync_cloudflare_config.mjs";

test("all Cloudflare rules are restricted to the production hostname", () => {
  assert.equal(MANAGED_RULES.length, 3);
  for (const { rule } of MANAGED_RULES) {
    assert.match(rule.expression, new RegExp(PRODUCTION_HOSTNAME.replaceAll(".", "\\.")));
    assert.equal(rule.enabled, true);
  }
});

test("configuration rule disables only injected performance runtime", () => {
  const configRule = MANAGED_RULES.find(
    ({ phase }) => phase === "http_config_settings",
  ).rule;
  assert.deepEqual(configRule.action_parameters, {
    disable_rum: true,
    rocket_loader: false,
  });
});

test("cache rule matches only fingerprinted or versioned resources", () => {
  const cacheRule = MANAGED_RULES.find(
    ({ phase }) => phase === "http_request_cache_settings",
  ).rule;
  assert.match(cacheRule.expression, /\/assets\/\*\.\*\.\*/);
  assert.match(cacheRule.expression, /violations_latest\.json/);
  assert.match(cacheRule.expression, /query contains "v="/);
  assert.doesNotMatch(cacheRule.expression, /manifest\.json/);
});

test("rule comparison ignores Cloudflare response metadata", () => {
  const desired = MANAGED_RULES[0].rule;
  assert.equal(
    rulesMatch({
      ...desired,
      id: "generated",
      ref: "generated-reference",
      version: "1",
    }, desired),
    true,
  );
});

test("updates preserve a dashboard rule's immutable generated reference", () => {
  const desired = MANAGED_RULES[0].rule;
  const update = ruleUpdateBody({ ...desired, ref: "generated-reference" }, desired);

  assert.equal("ref" in update, false);
  assert.equal(update.description, desired.description);
});

test("rule comparison ignores object key order returned by Cloudflare", () => {
  const desired = MANAGED_RULES[1].rule;
  const reordered = {
    expression: desired.expression,
    enabled: desired.enabled,
    description: desired.description,
    action_parameters: {
      edge_ttl: {
        mode: desired.action_parameters.edge_ttl.mode,
        default: desired.action_parameters.edge_ttl.default,
      },
      browser_ttl: {
        mode: desired.action_parameters.browser_ttl.mode,
        default: desired.action_parameters.browser_ttl.default,
      },
      cache: desired.action_parameters.cache,
    },
    action: desired.action,
    ref: desired.ref,
  };

  assert.equal(rulesMatch(reordered, desired), true);
});

test("rule comparison ignores explicit defaults returned by Cloudflare", () => {
  const desired = MANAGED_RULES[2].rule;
  const withDefaults = structuredClone(desired);
  withDefaults.action_parameters.immutable.cloudflare_only = false;
  withDefaults.action_parameters["max-age"].cloudflare_only = false;

  assert.equal(rulesMatch(withDefaults, desired), true);
});
