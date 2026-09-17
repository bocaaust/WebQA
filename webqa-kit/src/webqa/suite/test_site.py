from webqa.checks import journey_check, page_check


def test_site_case(loaded_page, case, site_config, case_output):
    if case["kind"] == "page":
        page_check(loaded_page, case["spec"], case["check"], case_output)
    else:
        journey_check(loaded_page, case["spec"], site_config, case_output)
