Changelog for Abilian SBE
=========================

0.2.6 (2016-05-06)
------------------

- Test fixes.

0.2.5 (2016-04-25)
------------------

- Fix unicode encoding issue.

0.2.2 (2016-03-03)
------------------

- Get rid of guess-language-spirit. Use langid instead.

0.2.1 (2016-02-15)
------------------

- Documents: can upload a new version if nobody has locked the document.
- Fix daily notifications (for wiki pages).

0.2.0 (2016-02-12)
------------------

Time for a minor release.

0.1.10 (2016-02-05)
-------------------

- forum reply by mail: changed reply address so that it's local part never
  exceeds 64 characters length

0.1.9 (2016-01-29)
------------------

- Fix error when sending the daily digest.

0.1.8 (2016-01-29)
------------------

- Fix packaging issue (missing .mo files).

0.1.7 (2016-01-29)
------------------

- Communities can be linked to a group. Members are 2-way synced.


0.1.5 (2015-11-20)
------------------

- Members: export listing in xslx format
- Documents are reindexed on permissions or membership change
- Conversations can be closed by admin for edit/new comments/deletion
- Fix global activity stream for non-admin users


0.1.4 (2015-08-07)
------------------

- Add "wall of attachments" in communities
- Use pdfjs to preview documents on browsers
- Fix 'refresh preview' action on documents
- UX/UI improvements


0.1.3 (2015-07-29)
------------------

- Various CSS and HTML improvements / fixes.


0.1.2 (2015-07-15)
------------------

Improvements
~~~~~~~~~~~~

- Design / CSS

Fixes
~~~~~

- Fix sqlalchemy connection issues with Celery tasks

Refactoring
~~~~~~~~~~~

- JS: Use requirejs


0.1.1 (2015-05-27)
------------------

Improvements
~~~~~~~~~~~~

*  community views: support graceful csrf failure
*  added attachment to forum post by email
*  added attachments views in forum
*  forum post: show 'send by mail' only if enabled for community or current user
*  i18n on roles

Fixes
~~~~~

* fix css rule for 'recent users' box
*  communities settings forms:  fix imagefield arguments
*  NavAction Communities is now only showed when authenticated
*  added regex clean forum posts from email

Refactoring
~~~~~~~~~~~

*  folder security: use Permission/Role objects
*  * views/social.py: remove before_request
*  forum views: use CBV
*  forum: form factorisation
*  @login_required on community index and social.wall, has_access() stops anonymous users
*  pep8 cleanup
*  tests/functional  port is now dynamic to avoid runtime errors
*  replaced csrf_field -> csrf.field() in thread.html to have proper csrf and allow action to go on (#16)
*  unescaped activity entry body_html
*  fix test: better mock of celery task
*  abilian-core removed extensions.celery; use periodic_task from abilian.core.celery
*  forum: in-mail tasks: set app default config values; conditionnaly register check_maildir
*  celery: use 'shared_task' decorator

0.1 (2015-03-31)
----------------

Initial release

