from ingest.cli import main


def test_dry_run(tmp_path, capsys):
    p = tmp_path / "acme.csv"
    p.write_text("order_id,sku,qty,amount,ordered_at,exported_at\nA-1,MUG-1,2,12.50,07/04/2026,\n")
    assert main(["acme", str(p), "--dry-run"]) == 0
    assert "parsed 1, quarantined 0 (dry run)" in capsys.readouterr().out
