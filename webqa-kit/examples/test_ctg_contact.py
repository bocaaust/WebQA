"""Managed pytest module. Revise with webqa revise; keep its .plan.json sidecar."""
import pytest
from webqa.checks import journey_check, page_check

@pytest.mark.functional
@pytest.mark.smoke
@pytest.mark.parametrize("case", [{'check': 'content',
 'id': 'authored--contact-heading',
 'kind': 'page',
 'priority': 'P0',
 'spec': {'checks': ['content'],
          'h1_contains': "We'd Love to Hear From You!",
          'id': 'contact',
          'language': 'en',
          'path': '/contact-us',
          'priority': 'P0',
          'title_contains': 'Contact',
          'viewports': ['desktop'],
          'why': 'Visitors should recognize the contact page'},
 'viewport': 'desktop'}],
                         ids=['authored--contact-heading'])
def test_contact_heading(loaded_page, case, site_config, case_output):
    page_check(loaded_page, case["spec"], case["check"], case_output)

@pytest.mark.accessibility
@pytest.mark.mobile
@pytest.mark.parametrize("case", [{'check': 'axe',
 'id': 'authored--contact-accessibility',
 'kind': 'page',
 'priority': 'P1',
 'spec': {'checks': ['axe'],
          'h1_contains': "We'd Love to Hear From You!",
          'id': 'contact',
          'language': 'en',
          'path': '/contact-us',
          'priority': 'P1',
          'title_contains': 'Contact',
          'viewports': ['mobile'],
          'why': 'Detect accessibility rule violations on a small screen'},
 'viewport': 'mobile'}],
                         ids=['authored--contact-accessibility'])
def test_contact_accessibility(loaded_page, case, site_config, case_output):
    page_check(loaded_page, case["spec"], case["check"], case_output)

@pytest.mark.accessibility
@pytest.mark.parametrize("case", [{'id': 'authored--contact-keyboard',
 'kind': 'journey',
 'priority': 'P1',
 'spec': {'accessibility': True,
          'id': 'contact-keyboard',
          'priority': 'P1',
          'start': '/contact-us',
          'steps': [{'action': 'tab-to', 'locator': {'label': 'Name'}, 'max_tabs': 30},
                    {'action': 'keyboard', 'value': 'Tab'},
                    {'action': 'expect', 'assert': 'focused', 'locator': {'label': 'Organization'}},
                    {'action': 'keyboard', 'value': 'Tab'},
                    {'action': 'expect',
                     'assert': 'focused',
                     'locator': {'label': 'Email Address'}},
                    {'action': 'keyboard', 'value': 'Tab'},
                    {'action': 'expect', 'assert': 'focused', 'locator': {'label': 'Phone Number'}},
                    {'action': 'keyboard', 'value': 'Tab'},
                    {'action': 'expect', 'assert': 'focused', 'locator': {'label': 'Message'}},
                    {'action': 'keyboard', 'value': 'Tab'},
                    {'action': 'expect',
                     'assert': 'focused',
                     'locator': {'name': 'Send Message', 'role': 'button'}}],
          'viewport': 'desktop',
          'why': 'Tab reaches each form field and then the submit control, without activating it.'},
 'viewport': 'desktop'}],
                         ids=['authored--contact-keyboard'])
def test_contact_keyboard(loaded_page, case, site_config, case_output):
    journey_check(loaded_page, case["spec"], site_config, case_output)

