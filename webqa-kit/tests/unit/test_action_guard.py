import pytest
from webqa.checks import prevent_submit_action


class Element:
    def __init__(self, is_submit, in_form=True):
        self.is_submit, self.in_form = is_submit, in_form

    def evaluate(self, expression):
        return self.is_submit if "el.tagName" in expression else self.in_form


def test_tab_can_leave_submit_button_but_activation_is_blocked():
    control = Element(True)
    prevent_submit_action(control, "press", "Tab")
    for action, key in [("click", None), ("press", "Enter"), ("press", "Space")]:
        with pytest.raises(AssertionError):
            prevent_submit_action(control, action, key)


def test_enter_in_form_input_is_blocked_but_menu_enter_is_allowed():
    with pytest.raises(AssertionError):
        prevent_submit_action(Element(False), "press", "Enter")
    prevent_submit_action(Element(False, False), "press", "Enter")
