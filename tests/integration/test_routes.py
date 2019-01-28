import re
import traceback
import warnings

from abilian.web import url_for

ENDPOINTS_TO_SKIP = frozenset(
    [
        "admin.audit_search_users",
        "search.search_main",
        "search.live",
        "notifications.debug_social",
        "social.groups_json",
        "social.groups_new",
        "social.users_json",
        "social.users_dt_json",
        "communities.community_default_image",
        "images.user_default",
    ]
)

PATTERNS_TO_SKIP = [r"^.*\.list_json2$", r"^setup\..*$"]


def get_all_rules(app):
    rules = sorted(app.url_map.iter_rules(), key=lambda x: x.endpoint)

    for rule in rules:
        if "GET" not in rule.methods:
            continue

        if rule.arguments:
            continue

        endpoint = rule.endpoint
        print(endpoint)

        # Skip several exceptions.
        if endpoint in ENDPOINTS_TO_SKIP:
            continue

        if any(re.match(p, endpoint) for p in PATTERNS_TO_SKIP):
            continue

        url = url_for(endpoint)

        if "/ajax/" in url:
            continue

        yield rule


def test_all_registered_urls(app, db, admin_user, client, req_ctx):
    warnings.filterwarnings("ignore")

    rules = get_all_rules(app)
    user = admin_user

    for rule in rules:
        with client.session_transaction() as session:
            session["user_id"] = user.id

            endpoint = rule.endpoint
            url = url_for(endpoint)
            try:
                response = client.get(url)
                assert response.status_code in (
                    200,
                    302,
                ), f"Bad link: {url} (status={response.status_code})"
            except BaseException:
                msg = f"Problem with endpoint: {endpoint} / url: {url}"
                print(msg)
                traceback.print_exc()
                raise
