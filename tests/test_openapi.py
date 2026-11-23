from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.mark.parametrize(
    "method,path,expected_codes",
    [
        ("get", "/api/analytics", {"200", "503"}),
        ("get", "/api/requests", {"200", "422", "503"}),
        ("post", "/api/requests", {"201", "422", "503"}),
        ("get", "/api/requests/{request_id}", {"200", "404", "422", "503"}),
        ("get", "/api/requests/{request_id}/position", {"200", "404", "422", "503"}),
        ("post", "/api/requests/{request_id}/claim", {"200", "404", "409", "422", "503"}),
        ("post", "/api/requests/{request_id}/start", {"200", "404", "409", "422", "503"}),
        ("post", "/api/requests/{request_id}/resolve", {"200", "404", "409", "422", "503"}),
    ],
)
def test_request_docs_describe_success_and_error_responses(settings, method, path, expected_codes):
    with TestClient(create_app(settings)) as client:
        schema = client.get("/openapi.json").json()

    responses = schema["paths"][path][method]["responses"]
    assert expected_codes == set(responses)
    for code in expected_codes & {"404", "409", "503"}:
        assert responses[code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ApiError"
        }
    assert schema["components"]["schemas"]["ApiError"]["properties"]["detail"]["type"] == "string"
