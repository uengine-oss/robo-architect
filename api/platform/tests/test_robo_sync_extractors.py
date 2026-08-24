import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[3]
EXTRACTORS = ROOT / "skills" / "robo-spec" / "robo-sync" / "extractors"


def _run(name: str, path: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(EXTRACTORS / name), str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_java_extracts_domain_fields_methods_events_and_enum(tmp_path):
    source = tmp_path / "Payment.java"
    source.write_text(
        """
        package domain;
        public class Payment {
            @jakarta.persistence.Id
            private final java.util.UUID paymentId;
            private State state;
            public enum State { INITIATED, APPROVED, REJECTED }
            @org.springframework.transaction.annotation.Transactional
            public void approve(java.util.UUID approverId) { this.state = State.APPROVED; }
            private void publish() {
                publisher.publish("payment", "id", "PaymentApproved", "corr", payload);
            }
        }
        """,
        encoding="utf-8",
    )

    result = _run("java_extract.py", source)
    assert result["name"] == "Payment"
    assert {field["name"] for field in result["fields"]} == {"paymentId", "state"}
    assert "approve" in {method["name"] for method in result["methods"]}
    assert result["emittedEvents"] == ["PaymentApproved"]
    assert result["enums"] == [{
        "name": "State", "values": ["INITIATED", "APPROVED", "REJECTED"]
    }]


def test_avro_extracts_nullable_and_default(tmp_path):
    schema = tmp_path / "ReturnApproved.avsc"
    schema.write_text(json.dumps({
        "type": "record",
        "name": "ReturnApproved",
        "namespace": "contracts.returns",
        "fields": [
            {"name": "returnRequestId", "type": "string"},
            {"name": "shipmentId", "type": ["null", "string"], "default": None},
        ],
    }), encoding="utf-8")

    result = _run("avro_extract.py", schema)
    assert result["kind"] == "Event"
    assert result["name"] == "ReturnApproved"
    assert result["fields"][0]["required"] is True
    assert result["fields"][1] == {
        "name": "shipmentId",
        "type": "null | string",
        "required": False,
        "hasDefault": True,
    }
