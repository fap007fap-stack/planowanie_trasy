from calculations import Cargo, score_route, select_vehicle


def test_transformer_scenario_selects_heavy_configuration():
    plan = select_vehicle(Cargo("Transformator", 48.0, 9.0, 3.8, 3.6))
    assert plan.gross_mass_t == 80.0
    assert plan.total_width_m == 3.8
    assert plan.total_height_m == 4.35
    assert plan.trailer_axles == 6
    assert plan.permit_category.startswith("V")
    assert plan.pilots == 2
    assert abs(sum(plan.axle_loads_t) - plan.gross_mass_t) < 0.1


def test_route_score_rewards_motorway_share():
    motorway = score_route(340, 7, 5, 0, 0.8)
    local = score_route(340, 7, 5, 0, 0.1)
    assert motorway < local


def test_light_machine_uses_smaller_configuration():
    plan = select_vehicle(
        Cargo("Koparka", 10.0, 7.0, 2.9, 3.1, category="Maszyna budowlana lub przemysłowa")
    )
    assert plan.total_axles == 5
    assert "najazdami" in plan.trailer


def test_long_cargo_uses_telescopic_trailer():
    plan = select_vehicle(
        Cargo("Łopata", 22.0, 34.0, 3.2, 3.4, category="Długi element konstrukcyjny / łopata")
    )
    assert "teleskopowa" in plan.trailer
    assert plan.total_length_m > 40

