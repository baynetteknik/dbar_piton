from .filter_tree import FilterTreeSidebar001
from .summary_card import SummaryCardSidebar001
from .git_left_sidebar import GitLeftSidebar
from .git_right_sidebar import GitRightSidebar

SIDEBAR_COMPONENTS = {
    "leftsidebar001": FilterTreeSidebar001,
    "rightsidebar001": SummaryCardSidebar001,
    "leftsidebar_git": GitLeftSidebar,
    "rightsidebar_git": GitRightSidebar,
}

