import io
import zipfile

import pytest
from openpyxl import Workbook

from app.core.checklist_import import ImportFileError, parse_checklist_file
from tests.conftest import auth
from tests.test_checklists import org  # noqa: F401  (fixture)

CSV = ("id,category,control,audit_step,reference\n"
       "C-1,Auth,Disable root login,Check sshd_config,CIS 5.2\n"
       "C-2,Logging,Enable auditd,Check service,CIS 4.1\n")


def upload(client, tokens, name, data, tech="Acme Custom App"):
    return client.post("/checklist-versions/import", headers=auth(tokens),
                       data={"technology": tech}, files={"file": (name, data)})


def test_csv_import_creates_unverified_draft(client, org):
    r = upload(client, org["auditor"], "my.csv", CSV)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["status"] == "draft" and j["source"] == "import" and j["total_controls"] == 2
    assert all(c["reference_verified"] is False for c in j["checklist"])
    # normal workflow still applies: submit then a different person approves
    vid = j["id"]
    assert client.post(f"/checklist-versions/{vid}/submit", headers=auth(org["auditor"])).status_code == 200
    assert client.post(f"/checklist-versions/{vid}/approve", headers=auth(org["reviewer"]),
                       json={"comment": "ok"}).status_code == 200


def test_json_xlsx_txt_import():
    ctrls, _ = parse_checklist_file("a.json", b'{"controls":[{"Control":"Do X","Audit Step":"Check X"}]}')
    assert ctrls[0]["control"] == "Do X" and ctrls[0]["audit_step"] == "Check X"
    wb = Workbook(); ws = wb.active
    ws.append(["Control ID", "Category", "Requirement"]); ws.append(["X-1", "Net", "Close port 23"])
    buf = io.BytesIO(); wb.save(buf)
    ctrls, warns = parse_checklist_file("a.xlsx", buf.getvalue())
    assert ctrls[0]["control_id"] == "X-1" and warns  # generic audit step warning
    ctrls, _ = parse_checklist_file("a.txt", b"# Auth\n- Disable root\n2. Use MFA\n")
    assert [c["category"] for c in ctrls] == ["Auth", "Auth"] and ctrls[1]["control"] == "Use MFA"


def test_formula_injection_is_neutralised():
    ctrls, _ = parse_checklist_file("a.csv", b"control\n=cmd|' /C calc'!A0\n")
    assert ctrls[0]["control"].startswith("'=")


@pytest.mark.parametrize("name,data,msg", [
    ("a.exe", b"MZ", "Unsupported"),
    ("a.csv", b"", "empty"),
    ("a.csv", b"control\n" + b"x\n" * 501, "Too many"),
    ("a.csv", b"control,id\nA,1\nB,1\n", "duplicate"),
    ("a.csv", b"control\n" + b"x" * 4001 + b"\n", "longer"),
    ("a.json", b"{not json", "Invalid JSON"),
    ("a.xlsx", b"not a zip", "not a valid"),
    ("a.csv", b"foo,bar\n1,2\n", "No controls"),
    ("a.csv", b"x" * (2 * 1024 * 1024 + 1), "larger"),
])
def test_bad_files_rejected(name, data, msg):
    with pytest.raises(ImportFileError, match=msg):
        parse_checklist_file(name, data)


def test_zip_bomb_xlsx_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.xml", b"0" * (25 * 1024 * 1024))
    assert len(buf.getvalue()) < 100_000
    with pytest.raises(ImportFileError, match="too large"):
        parse_checklist_file("bomb.xlsx", buf.getvalue())


def test_import_permissions_and_errors(client, org):
    assert upload(client, org["read_only"], "my.csv", CSV).status_code == 403
    assert upload(client, org["reviewer"], "my.csv", CSV).status_code == 403
    bad = upload(client, org["auditor"], "evil.exe", b"MZ")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_import_file"
    assert upload(client, org["auditor"], "my.csv", CSV).status_code == 201
    assert upload(client, org["auditor"], "my.csv", CSV).status_code == 409  # open draft exists


def test_ai_generate_returns_full_baseline(client, org):
    r = client.get("/checklists/AWS%20API%20Gateway/generate", headers=auth(org["auditor"]))
    assert r.status_code == 200 and r.json()["total_controls"] >= 10
