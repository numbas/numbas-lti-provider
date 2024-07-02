Accessibility statement
=======================

Numbas should be accessible to everyone who needs to or would like to use it.

Accessibility is an important consideration during the design and development process.
We regularly test the Numbas LTI provider against a variety of accessibility requirements.

We have designed the Numbas LTI provider to satisfy the WCAG 2.2 criteria at the AAA level.

This statement was prepared in July 2024.

What's covered by this statement
################################

Pages served by the Numbas LTI provider, including student, instructor and admin pages.

What's not covered by this statement
####################################

The Numbas exam interface and the Numbas editor, which are covered by their own accessibility statements:

* `Numbas exam accessibility statement <https://docs.numbas.org.uk/en/latest/accessibility/exam.html>`__
* `Numbas editor accessibility statement <https://docs.numbas.org.uk/en/latest/accessibility/editor.html>`__

Accessibility conformance report
################################

We have written an accessibility conformance report, following the :abbr:`VPAT (Voluntary Product Accessibility Template)`.

This report describes in detail how we meet each of the criteria or places where the criteria are not met.

:ref:`vpat`.

Known problems
##############

The following aspects of the Numbas LTI provider's interface have accessibility problems:

* The :ref:`resource statistics <resource-statistics>` page is quite hard to use with a screen reader.
  The graphics are not very well described in text.
  We are planning to redesign this page.

* Colours differentiating between different types of text (success and danger for example) have a lower contrast ratio to the background, meeting the AA threshold, in the interest of them being distinguishable from each other.
  These colours are most often used on buttons and are never used for more than a few words together.

* The user can't select their own foreground and background colours, other than to switch to a dark colour scheme.
