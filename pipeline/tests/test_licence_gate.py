"""The licence gate views in schema.sql must catch each kind of leak."""
from pathlib import Path

import duckdb
import pytest

SCHEMA = Path(__file__).resolve().parents[1] / "schema.sql"


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute(SCHEMA.read_text(encoding="utf-8"))
    c.execute("""INSERT INTO sources VALUES
      ('green','G','g','u','CC BY 4.0',null,'green',true,true,false,false,'a','2026-10-24',null),
      ('nomod','N','n','u','CC BY 4.0',null,'green',true,true,false,true,'a','2026-10-24',null),
      ('sa','S','s','u','CC BY-SA 4.0',null,'green',true,true,true,false,'a','2026-10-24',null),
      ('amber','A','x','u','permission',null,'amber',false,false,false,false,'a','2026-10-24',null)""")
    c.execute("""INSERT INTO source_releases VALUES
      ('g@1','green',null,null,now(),'p','h',1,0), ('n@1','nomod',null,null,now(),'p','h',1,0),
      ('s@1','sa',null,null,now(),'p','h',1,0), ('a@1','amber',null,null,now(),'p','h',1,0)""")
    c.execute("INSERT INTO entities VALUES ('IND','country','india','India','IND',null,null,null)")
    return c


def add_indicator(c, iid, source, applies=("country",), display_only=False):
    c.execute("INSERT INTO indicators VALUES (?,?,null,null,?,'d','u','higher_better','x',?,null,null,null,2,?)",
              [iid, source, iid, list(applies), display_only])
    c.execute("INSERT INTO observations VALUES ('IND',?,2024,1,'measured',?,null)", [iid, f"{source[0]}@1"])


def add_ranking(c, weights):
    c.execute("INSERT INTO rankings VALUES ('r','1','original_composite','R','country',null,'{}','min_max',"
              "'pillars',0.7,10,0.25,1,2024,5,'CC-BY-4.0','m',null)")
    for pillar, pw, iid, w in weights:
        c.execute("INSERT INTO ranking_weights VALUES ('r','1',?,?,?,?,null,null)", [pillar, pw, iid, w])


def rows(c, view):
    return c.execute(f"SELECT * FROM {view}").fetchall()


def test_clean_release_passes(con):
    add_indicator(con, "ok", "green")
    add_ranking(con, [("p", 1.0, "ok", 1.0)])
    for v in ("gate_non_green_published", "gate_licence_leak_into_composite",
              "gate_inapplicable_indicator", "gate_bad_weights"):
        assert rows(con, v) == []


def test_amber_source_cannot_be_published(con):
    add_indicator(con, "imf", "amber")
    assert rows(con, "gate_non_green_published") == [("imf", "amber", "amber")]


@pytest.mark.parametrize("source,display_only", [("nomod", False), ("sa", False), ("green", True)])
def test_restricted_inputs_cannot_feed_a_cc_by_composite(con, source, display_only):
    add_indicator(con, "x", source, display_only=display_only)
    add_ranking(con, [("p", 1.0, "x", 1.0)])
    assert len(rows(con, "gate_licence_leak_into_composite")) == 1


def test_indicator_must_apply_to_entity_type(con):
    add_indicator(con, "c", "green", applies=("city",))
    add_ranking(con, [("p", 1.0, "c", 1.0)])
    assert len(rows(con, "gate_inapplicable_indicator")) == 1


def test_weights_must_sum_to_one(con):
    add_indicator(con, "a", "green")
    add_indicator(con, "b", "green")
    add_ranking(con, [("p1", 0.6, "a", 1.0), ("p2", 0.3, "b", 1.0)])
    assert rows(con, "gate_bad_weights")
