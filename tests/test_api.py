"""End-to-end coverage of the auth, numerology, report and admin surfaces."""

B = "/api/v1"


class TestMeta:
    def test_health(self, client):
        assert client.get(f"{B}/health").json()["status"] == "ok"

    def test_public_config_lists_modules(self, client):
        cfg = client.get(f"{B}/config").json()
        assert {m["key"] for m in cfg["modules"]} == {"name", "mobile", "vehicle"}


class TestSignupFlow:
    def test_three_step_signup(self, client):
        email = "flow@example.com"
        start = client.post(f"{B}/auth/signup/start", json={"email": email})
        assert start.status_code == 200
        otp = start.json()["dev_otp"]

        bad = client.post(f"{B}/auth/signup/verify", json={"email": email, "code": "000000"})
        assert bad.status_code == 400
        assert "attempt" in bad.json()["message"]

        good = client.post(f"{B}/auth/signup/verify", json={"email": email, "code": otp})
        assert good.status_code == 200

        done = client.post(
            f"{B}/auth/signup/complete",
            json={
                "signup_token": good.json()["signup_token"],
                "full_name": "Flow Tester",
                "phone": "9876543210",
                "password": "Flow123456",
            },
        )
        assert done.status_code == 200
        assert done.json()["user"]["is_email_verified"] is True

    def test_duplicate_email_is_rejected(self, client):
        assert (
            client.post(f"{B}/auth/signup/start", json={"email": "flow@example.com"}).status_code
            == 409
        )

    def test_weak_password_is_rejected(self, client):
        email = "weak@example.com"
        otp = client.post(f"{B}/auth/signup/start", json={"email": email}).json()["dev_otp"]
        token = client.post(f"{B}/auth/signup/verify", json={"email": email, "code": otp}).json()[
            "signup_token"
        ]
        res = client.post(
            f"{B}/auth/signup/complete",
            json={
                "signup_token": token,
                "full_name": "Weak",
                "phone": "9876543210",
                "password": "onlyletters",
            },
        )
        assert res.status_code == 422
        assert "letters and numbers" in res.json()["message"]


class TestAuth:
    def test_login_and_me(self, client, user_headers):
        assert client.get(f"{B}/auth/me", headers=user_headers).json()["email"] == "tester@example.com"

    def test_wrong_password(self, client):
        res = client.post(
            f"{B}/auth/login", json={"email": "tester@example.com", "password": "nope12345"}
        )
        assert res.status_code == 401

    def test_protected_route_requires_a_token(self, client):
        assert client.get(f"{B}/auth/me").status_code == 401

    def test_profile_update(self, client, user_headers):
        res = client.patch(f"{B}/auth/me", headers=user_headers, json={"birth_place": "Kolkata"})
        assert res.json()["birth_place"] == "Kolkata"


class TestNumerologyEndpoints:
    def test_name_quick_is_public(self, client):
        res = client.post(f"{B}/numerology/name/quick", json={"name": "Pankaj Kabiraj"})
        assert res.status_code == 200
        assert res.json()["result"]["compound"] == 28
        assert res.json()["saved"] is False  # anonymous results are not stored

    def test_name_quick_saves_for_signed_in_users(self, client, user_headers):
        res = client.post(
            f"{B}/numerology/name/quick", headers=user_headers, json={"name": "Pankaj Kabiraj"}
        )
        assert res.json()["saved"] is True
        assert res.json()["report_id"]

    def test_full_report_requires_auth(self, client):
        res = client.post(
            f"{B}/numerology/name/full", json={"name": "Pankaj Kabiraj", "dob": "1995-08-15"}
        )
        assert res.status_code == 401

    def test_full_report_then_quota(self, client, user_headers):
        first = client.post(
            f"{B}/numerology/name/full",
            headers=user_headers,
            json={"name": "Pankaj Kabiraj", "dob": "1995-08-15"},
        )
        assert first.status_code == 200
        assert first.json()["result"]["similar_names"]

        second = client.post(
            f"{B}/numerology/name/full",
            headers=user_headers,
            json={"name": "Someone Else", "dob": "1995-08-15"},
        )
        assert second.status_code == 402

    def test_mobile(self, client, user_headers):
        res = client.post(f"{B}/numerology/mobile", headers=user_headers, json={"number": "9531199355"})
        body = res.json()["result"]
        assert body["compound"] == 50 and body["total"] == 5
        assert len(body["grid"]) == 9

    def test_mobile_compare(self, client, user_headers):
        res = client.post(
            f"{B}/numerology/mobile/compare",
            headers=user_headers,
            json={"current": "9531199355", "candidate": "8888888888"},
        )
        assert res.json()["result"]["comparison"]["better"] in ("current", "candidate", "same")

    def test_vehicle_and_suggestions(self, client, user_headers):
        res = client.post(
            f"{B}/numerology/vehicle", headers=user_headers, json={"registration": "WB 06 AB 1234"}
        )
        assert res.json()["result"]["running_number"] == "1234"

        sug = client.post(f"{B}/numerology/vehicle/suggest", json={"dob": "1995-08-15", "length": 4})
        assert len(sug.json()["result"]["suggestions"]) > 0

    def test_newborn(self, client):
        res = client.post(f"{B}/numerology/newborn", json={"dob": "2026-08-28"})
        assert res.json()["result"]["start_letters"]

    def test_reference_tables(self, client):
        assert len(client.get(f"{B}/numerology/reference/numbers").json()) == 9
        assert len(client.get(f"{B}/numerology/reference/pairs").json()) == 81
        assert len(client.get(f"{B}/numerology/reference/compounds").json()) == 52


class TestReports:
    def test_list_and_fetch(self, client, user_headers):
        listing = client.get(f"{B}/reports", headers=user_headers).json()
        assert listing["total"] > 0
        rid = listing["items"][0]["id"]
        assert client.get(f"{B}/reports/{rid}", headers=user_headers).json()["id"] == rid

    def test_pdf_download(self, client, user_headers):
        rid = client.get(f"{B}/reports", headers=user_headers).json()["items"][0]["id"]
        res = client.get(f"{B}/reports/{rid}/pdf", headers=user_headers)
        assert res.status_code == 200
        assert res.content[:4] == b"%PDF"

    def test_cannot_read_another_users_report(self, client, user_headers, admin_headers):
        rid = client.get(f"{B}/reports", headers=user_headers).json()["items"][0]["id"]
        assert client.get(f"{B}/reports/{rid}", headers=admin_headers).status_code == 404


class TestAdmin:
    def test_users_cannot_reach_the_admin_api(self, client, user_headers):
        assert client.get(f"{B}/admin/stats", headers=user_headers).status_code == 403

    def test_stats(self, client, admin_headers):
        stats = client.get(f"{B}/admin/stats", headers=admin_headers).json()
        assert stats["users_total"] >= 1
        assert len(stats["signups_series"]) == 30

    def test_user_listing_and_search(self, client, admin_headers):
        res = client.get(f"{B}/admin/users?q=tester@example.com", headers=admin_headers).json()
        assert res["total"] == 1
        assert res["items"][0]["email"] == "tester@example.com"
        # partial matches hit both name and email columns
        assert client.get(f"{B}/admin/users?q=tester", headers=admin_headers).json()["total"] >= 1

    def test_rule_override_goes_live_then_reverts(self, client, admin_headers):
        client.put(
            f"{B}/admin/rules",
            headers=admin_headers,
            json={"kind": "compound_meanings", "key": "28", "data": {"short": "CUSTOM TEXT"}},
        )
        assert (
            client.post(f"{B}/numerology/name/quick", json={"name": "Pankaj Kabiraj"}).json()[
                "result"
            ]["short"]
            == "CUSTOM TEXT"
        )

        client.delete(f"{B}/admin/rules/compound_meanings/28", headers=admin_headers)
        assert (
            "again and again"
            in client.post(f"{B}/numerology/name/quick", json={"name": "Pankaj Kabiraj"}).json()[
                "result"
            ]["short"]
        )

    def test_settings_roundtrip(self, client, admin_headers):
        client.put(
            f"{B}/admin/settings",
            headers=admin_headers,
            json={"key": "premium_price_inr", "value": {"value": 799}},
        )
        assert client.get(f"{B}/config").json()["premium_price_inr"] == 799

    def test_audit_log_records_admin_actions(self, client, admin_headers):
        actions = {
            a["action"] for a in client.get(f"{B}/admin/audit", headers=admin_headers).json()["items"]
        }
        assert "rule.update" in actions and "setting.update" in actions


class TestMongoSpecifics:
    def test_many_password_only_users_can_coexist(self, client):
        """Regression: a sparse unique index on google_id collides on explicit nulls,
        which would reject every password signup after the first."""
        created = []
        for i in range(3):
            email = f"nogoogle{i}@example.com"
            otp = client.post(f"{B}/auth/signup/start", json={"email": email}).json()["dev_otp"]
            token = client.post(
                f"{B}/auth/signup/verify", json={"email": email, "code": otp}
            ).json()["signup_token"]
            res = client.post(
                f"{B}/auth/signup/complete",
                json={
                    "signup_token": token,
                    "full_name": f"No Google {i}",
                    "phone": "9876543210",
                    "password": "Password123",
                },
            )
            assert res.status_code == 200, res.json()
            created.append(res.json()["user"]["id"])
        assert len(set(created)) == 3

    def test_health_reports_the_database(self, client):
        assert client.get(f"{B}/health").json()["database"] == "up"

    def test_deleting_a_user_removes_their_reports(self, client, admin_headers):
        email = "cascade@example.com"
        otp = client.post(f"{B}/auth/signup/start", json={"email": email}).json()["dev_otp"]
        token = client.post(f"{B}/auth/signup/verify", json={"email": email, "code": otp}).json()[
            "signup_token"
        ]
        session = client.post(
            f"{B}/auth/signup/complete",
            json={
                "signup_token": token,
                "full_name": "Cascade User",
                "phone": "9876543211",
                "password": "Cascade123",
            },
        ).json()
        headers = {"Authorization": f"Bearer {session['access_token']}"}
        # a registration no other test uses, so the search below is unambiguous
        client.post(
            f"{B}/numerology/vehicle", headers=headers, json={"registration": "WB 99 ZZ 4321"}
        )
        assert client.get(f"{B}/reports", headers=headers).json()["total"] == 1
        assert client.get(f"{B}/admin/reports?q=WB 99 ZZ", headers=admin_headers).json()["total"] == 1

        uid = session["user"]["id"]
        assert client.delete(f"{B}/admin/users/{uid}", headers=admin_headers).status_code == 204
        assert client.get(f"{B}/admin/users/{uid}", headers=admin_headers).status_code == 404
        # Mongo has no cascading deletes, so the reports must be removed explicitly
        assert client.get(f"{B}/admin/reports?q=WB 99 ZZ", headers=admin_headers).json()["total"] == 0


class TestUploads:
    """Cloudinary is disabled in tests, so these assert the graceful fallbacks."""

    def test_avatar_rejects_a_non_image(self, client, user_headers):
        res = client.post(
            f"{B}/auth/me/avatar",
            headers=user_headers,
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert res.status_code == 400
        assert "JPG" in res.json()["message"]

    def test_avatar_upload_degrades_when_storage_is_off(self, client, user_headers):
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
        res = client.post(
            f"{B}/auth/me/avatar",
            headers=user_headers,
            files={"file": ("me.png", png, "image/png")},
        )
        assert res.status_code == 503

    def test_share_falls_back_to_the_api_link(self, client, user_headers):
        """With Cloudinary off the share link points at our own public endpoint,
        so sharing keeps working either way."""
        rid = client.get(f"{B}/reports", headers=user_headers).json()["items"][0]["id"]
        res = client.post(f"{B}/reports/{rid}/share", headers=user_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["source"] == "api"
        assert body["cdn_url"] is None
        assert f"/public/reports/{rid}" in body["url"]

    def test_shared_link_opens_without_a_token_header(self, client, user_headers):
        rid = client.get(f"{B}/reports", headers=user_headers).json()["items"][0]["id"]
        url = client.post(f"{B}/reports/{rid}/share", headers=user_headers).json()["url"]
        path = url.split("/api/v1", 1)[1]
        res = client.get(f"{B}{path}")          # deliberately no Authorization header
        assert res.status_code == 200
        assert res.content[:4] == b"%PDF"

    def test_share_token_cannot_be_forged(self, client, user_headers):
        rid = client.get(f"{B}/reports", headers=user_headers).json()["items"][0]["id"]
        assert client.get(f"{B}/public/reports/{rid}?t=forged.token.value").status_code == 403

    def test_share_token_is_bound_to_one_report(self, client, user_headers):
        items = client.get(f"{B}/reports", headers=user_headers).json()["items"]
        a, b = items[0]["id"], items[1]["id"]
        token = client.post(f"{B}/reports/{a}/share", headers=user_headers).json()["url"].split("t=")[1]
        assert client.get(f"{B}/public/reports/{b}?t={token}").status_code == 403

    def test_config_reports_upload_availability(self, client):
        assert client.get(f"{B}/config").json()["uploads_enabled"] is False
