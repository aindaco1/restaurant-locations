from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
FILTER_CONTROLS = ROOT / "_includes" / "filter-controls.html"


def load_controls():
    return BeautifulSoup(FILTER_CONTROLS.read_text(encoding="utf-8"), "html.parser")


def test_form_controls_have_unique_ids_and_names():
    soup = load_controls()
    controls = soup.find_all(["input", "select", "textarea"])

    assert controls
    assert all(control.get("id") for control in controls)
    assert all(control.get("name") for control in controls)
    assert len({control["id"] for control in controls}) == len(controls)
    assert len({control["name"] for control in controls}) == len(controls)


def test_labels_are_associated_with_form_controls():
    soup = load_controls()

    for label in soup.find_all("label"):
        target_id = label.get("for")
        assert target_id, f"Label has no for attribute: {label}"
        target = soup.find(id=target_id)
        assert target is not None, f"Label target does not exist: {target_id}"
        assert target.name in {"input", "select", "textarea"}


def test_severity_buttons_have_a_programmatic_group_label():
    soup = load_controls()
    heading = soup.find(id="mobile-severity-label")
    group = soup.find(attrs={"role": "group", "aria-labelledby": "mobile-severity-label"})

    assert heading is not None
    assert heading.name != "label"
    assert group is not None
    assert group.find_all("button")
