"""
Tests unitaires du pipeline BWF.
Aucune connexion DB ni réseau — tout est mocké.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from bwf.scrapers.tournaments import (
    parse_prize_money,
    _infer_category_id,
    fetch_tournaments_for_year,
)
from bwf.scrapers.matches import (
    parse_seed,
    is_singles,
    is_valid_score,
    parse_match_time,
    upsert_player,
)


# ---------------------------------------------------------------------------
# tournaments.py
# ---------------------------------------------------------------------------

class TestParsePrizeMoney:
    def test_standard(self):
        assert parse_prize_money("1,450,000") == 1450000

    def test_small(self):
        assert parse_prize_money("500,000") == 500000

    def test_none(self):
        assert parse_prize_money(None) is None

    def test_empty(self):
        assert parse_prize_money("") is None


class TestInferCategoryId:
    def test_finals(self):
        assert _infer_category_id("HSBC BWF World Tour Finals") == 22

    def test_super_1000(self):
        assert _infer_category_id("HSBC BWF World Tour Super 1000") == 23

    def test_super_750(self):
        assert _infer_category_id("HSBC BWF World Tour Super 750") == 24

    def test_super_500(self):
        assert _infer_category_id("HSBC BWF World Tour Super 500") == 25

    def test_super_300(self):
        assert _infer_category_id("HSBC BWF World Tour Super 300") == 26

    def test_unknown_defaults_to_300(self):
        assert _infer_category_id("Unknown Category") == 26


class TestFetchTournamentsForYear:
    def test_parses_months_correctly(self):
        """Vérifie que la liste est bien dépilée depuis la structure mois/tournois."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "month": "January",
                    "monthNo": 1,
                    "tournaments": [
                        {"id": 1, "name": "T1"},
                        {"id": 2, "name": "T2"},
                    ],
                },
                {
                    "month": "February",
                    "monthNo": 2,
                    "tournaments": [
                        {"id": 3, "name": "T3"},
                    ],
                },
            ]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        result = fetch_tournaments_for_year(2026, mock_client)

        assert len(result) == 3
        assert result[0]["name"] == "T1"
        assert result[2]["name"] == "T3"

    def test_empty_year(self):
        """Une année sans tournois retourne une liste vide."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        result = fetch_tournaments_for_year(2020, mock_client)
        assert result == []


# ---------------------------------------------------------------------------
# matches.py
# ---------------------------------------------------------------------------

class TestParseSeed:
    def test_valid(self):
        assert parse_seed("1") == 1
        assert parse_seed("8") == 8

    def test_none(self):
        assert parse_seed(None) is None

    def test_invalid(self):
        assert parse_seed("abc") is None


class TestIsSingles:
    def test_ms(self):
        assert is_singles({"eventName": "MS"}) is True

    def test_ws(self):
        assert is_singles({"eventName": "WS"}) is True

    def test_md(self):
        assert is_singles({"eventName": "MD"}) is False

    def test_wd(self):
        assert is_singles({"eventName": "WD"}) is False

    def test_xd(self):
        assert is_singles({"eventName": "XD"}) is False


class TestIsValidScore:
    def test_normal_with_score(self):
        match = {
            "scoreStatus": 0,
            "score": [{"set": 1, "home": 21, "away": 15}],
        }
        assert is_valid_score(match) is True

    def test_walkover(self):
        assert is_valid_score({"scoreStatus": 1, "score": []}) is False

    def test_empty_score(self):
        assert is_valid_score({"scoreStatus": 0, "score": []}) is False

    def test_three_sets(self):
        match = {
            "scoreStatus": 0,
            "score": [
                {"set": 1, "home": 21, "away": 18},
                {"set": 2, "home": 18, "away": 21},
                {"set": 3, "home": 21, "away": 15},
            ],
        }
        assert is_valid_score(match) is True


class TestParseMatchTime:
    def test_valid(self):
        result = parse_match_time("2026-05-17 05:00:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 5

    def test_none(self):
        assert parse_match_time(None) is None

    def test_invalid(self):
        assert parse_match_time("not-a-date") is None


class TestUpsertPlayer:
    def test_calls_execute(self):
        """Vérifie que upsert_player appelle bien session.execute."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one.return_value = 42

        player_data = {
            "id": "88135",
            "firstName": "Rin",
            "lastName": "IWANAGA",
            "nameDisplay": "Rin IWANAGA",
            "countryCode": "JPN",
        }

        result = upsert_player(mock_session, player_data)
        assert result == 42
        assert mock_session.execute.called
        assert mock_session.flush.called

    def test_missing_optional_fields(self):
        """Fonctionne même sans firstName/lastName."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one.return_value = 1

        player_data = {
            "id": "99999",
            "nameDisplay": "Unknown Player",
        }
        # Ne doit pas lever d'exception
        upsert_player(mock_session, player_data)