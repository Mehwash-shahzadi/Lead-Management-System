import pytest

from httpx import ASGITransport, AsyncClient

from app.main import app


class TestCORSMiddleware:
    """Verify that CORS headers are present on responses."""

    @pytest.mark.asyncio
    async def test_cors_headers_on_preflight(self):
        """OPTIONS request should return Access-Control-Allow-Origin."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_headers_on_get(self):
        """GET requests should include CORS response headers with configured origins."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/health",
                headers={"Origin": "http://localhost:3000"},
            )
            assert response.status_code == 200
            # CORS should return the specific allowed origin, not wildcard "*"
            assert (
                response.headers.get("access-control-allow-origin")
                == "http://localhost:3000"
            )


class TestHealthEndpoint:
    """Verify the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}


class TestValidationErrorFormat:
    """Verify that Pydantic validation errors return the custom format."""

    @pytest.mark.asyncio
    async def test_invalid_capture_body_returns_422(self):
        """Posting an empty body to /leads/capture should return 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/leads/capture", json={})
            assert response.status_code == 422
            body = response.json()
            assert body["type"] == "validation_error"
            assert "errors" in body

    @pytest.mark.asyncio
    async def test_invalid_phone_format_returns_422(self):
        """A phone number not matching +971XXXXXXXXX should fail validation."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/leads/capture",
                json={
                    "source_type": "bayut",
                    "lead_data": {
                        "first_name": "Test",
                        "last_name": "User",
                        "phone": "12345",  # invalid
                        "nationality": "UAE",
                        "language_preference": "english",
                        "budget_min": 100000,
                        "budget_max": 500000,
                        "property_type": "apartment",
                        "preferred_areas": ["Marina"],
                    },
                    "source_details": {},
                },
            )
            assert response.status_code == 422
