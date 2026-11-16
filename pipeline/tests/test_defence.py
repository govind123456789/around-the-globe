import json
import zipfile

from pipeline import defence


def _country(forces, service=None, milex=None, space=False, terror=None, name="Testland"):
    mil = {"Military and security forces": {"text": forces}}
    if service:
        mil["Military service age and obligation"] = {"text": service, "note": "<strong>note: </strong>women serve&nbsp;too"}
    if milex:
        mil["Military expenditures"] = {f"Military Expenditures {y}": {"text": f"{v}% of GDP ({y} est.)"} for y, v in milex}
    d = {"Government": {"Country name": {"conventional short form": {"text": name}}}, "Military and Security": mil}
    if space:
        d["Space"] = {"Space agency/agencies": {"text": "Test Space Agency (2025)"}}
    if terror:
        d["Terrorism"] = {"Terrorist group(s)": {"text": terror}}
    return d


def test_clean_and_milex():
    assert defence.clean("a<br><br>b &rsquo;c&nbsp;d <strong>x</strong>") == "a\n\nb ’c d x"
    p = defence.parse(_country("Army, Navy (2025)", milex=[(2024, 2.5), (2020, "1")]))
    assert p["milex"] == [(2020, 1.0), (2024, 2.5)]
    assert p["year"] == 2025


def test_service_status():
    s = defence.service_status
    assert s("no regular military forces; police only", "") == "none"
    assert s("Army", "18 years of age for compulsory military service; 12-month obligation (2025)") == "conscription"
    assert s("Army", "18 years for voluntary service; conscription abolished in 2011 (2025)") == "voluntary"
    assert s("Army", "17 years for voluntary service; requirement for compulsory military service was suspended in 1997") == "voluntary"
    assert s("Army", "17-23 for voluntary service (must have completed compulsory full-time education)") == "voluntary"
    assert s("Army", "") is None


def test_load_maps_codes_and_names(tmp_path, monkeypatch):
    z = tmp_path / "fb.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("factbook.json-master/europe/nl.json", json.dumps(_country("Dutch Army (2025)", "voluntary service", [(2024, 2.0)], space=True)))
        f.writestr("factbook.json-master/asia/zz.json", json.dumps(_country("Army", terror="Group A; Group B", name="Elsewhere")))
        f.writestr("factbook.json-master/world/xx.json", json.dumps(_country("none")))
    monkeypatch.setattr(defence, "_fips", lambda: {})
    out = defence.load({"NLD", "ELS"}, lambda n: "ELS" if n == "Elsewhere" else None, z)
    assert set(out) == {"NLD", "ELS"}
    assert out["NLD"]["status"] == "voluntary" and out["NLD"]["space"]["agency"]["text"] == ["Test Space Agency (2025)"]
    assert out["NLD"]["service"]["note"] == ["Note: women serve too"]
    assert out["ELS"]["terror"] == ["Group A", "Group B"]
    by_id = {"NLD": {"entity_id": "NLD", "name": "Netherlands"}, "ELS": {"entity_id": "ELS", "name": "Elsewhere"}}
    sm = defence.summary(out, by_id)
    assert [r["e"]["entity_id"] for r in sm["spend"]] == ["NLD"] and sm["spend"][0]["rank"] == 1
    assert [e["name"] for e in sm["space"]] == ["Netherlands"]


def test_missing_file_is_empty(tmp_path):
    assert defence.load({"NLD"}, None, tmp_path / "missing.zip") == {}
