.. _vpat:

Numbas LTI provider Accessibility Conformance Report, WCAG Edition
==================================================================

(Based on `VPAT® Version 2.5 WCAG <https://www.itic.org/policy/accessibility/vpat>`__)

Name of Product/Version:
    Numbas LTI provider v4.0.

Report Date:
    June 2024.

Product Description:
    This report covers the Numbas LTI provider interface.
    It does not cover the Numbas editor or the Numbas exam interface.

Contact Information:
    Email numbas@ncl.ac.uk.

    You can report bugs or make suggestions at `github.com/numbas/numbas-lti-provider/issues <https://github.com/numbas/numbas-lti-provider/issues>`__.

Notes
    .. todo::
        
        Fill this in.

Evaluation Methods Used:
    The following applications were used in this evaluation:
    
    * Desktop browsers: Safari on macOS with VoiceOver, Firefox on Linux, Chrome and Edge on Windows with NVDA.
    * Mobile browsers: Safari on iOS with VoiceOver.
    * Accessibility testing tools: Firefox developer tools.

    Most of the evaluation was performed by Laura Midgley, with some input from Christian Lawson-Perfect.

Applicable Standards/Guidelines
-------------------------------

This report covers the degree of conformance for the Web Content Accessibility Guidelines (WCAG) 2.2, at Levels A, AA and AAA.

Terms
-----

The terms used in the Conformance Level information are defined as follows:

Supports
    The functionality of the product has at least one method that meets the criterion without known defects or meets with equivalent facilitation.
Partially Supports
    Some functionality of the product does not meet the criterion.
Does Not Support
    The majority of product functionality does not meet the criterion.
Not Applicable
    The criterion is not relevant to the product.

WCAG 2.2 Report
---------------

Table 1: Success Criteria, Level A
**********************************

.. list-table::
  :header-rows: 1

  - 

     - Criteria
     - Conformance Level
     - Remarks and Explanations
  -
    - .. _vpat-non-text-content:
        
      `1.1.1: Non-text Content <https://www.w3.org/WAI/WCAG22/quickref/#non-text-content>`__ (Level A)
    - Partially supports
    - The graphs on the resource statistics page are not very well described.
  -
    - .. _vpat-audio-only-and-video-only-prerecorded:
        
      `1.2.1: Audio-only and Video-only (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#audio-only-and-video-only-prerecorded>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-captions-prerecorded:
        
      `1.2.2: Captions (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#captions-prerecorded>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-audio-description-or-media-alternative-prerecorded:
        
      `1.2.3: Audio Description or Media Alternative (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#audio-description-or-media-alternative-prerecorded>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-info-and-relationships:
        
      `1.3.1: Info and Relationships <https://www.w3.org/WAI/WCAG22/quickref/#info-and-relationships>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-meaningful-sequence:
        
      `1.3.2: Meaningful Sequence <https://www.w3.org/WAI/WCAG22/quickref/#meaningful-sequence>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-sensory-characteristics:
        
      `1.3.3: Sensory Characteristics <https://www.w3.org/WAI/WCAG22/quickref/#sensory-characteristics>`__ (Level A)
    - Supports
    - All interactive elements are clearly labelled in text.
  -
    - .. _vpat-use-of-color:
        
      `1.4.1: Use of Color <https://www.w3.org/WAI/WCAG22/quickref/#use-of-color>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-audio-control:
        
      `1.4.2: Audio Control <https://www.w3.org/WAI/WCAG22/quickref/#audio-control>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-keyboard:
        
      `2.1.1: Keyboard <https://www.w3.org/WAI/WCAG22/quickref/#keyboard>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-no-keyboard-trap:
        
      `2.1.2: No Keyboard Trap <https://www.w3.org/WAI/WCAG22/quickref/#no-keyboard-trap>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-character-key-shortcuts:
        
      `2.1.4: Character Key Shortcuts <https://www.w3.org/WAI/WCAG22/quickref/#character-key-shortcuts>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-timing-adjustable:
        
      `2.2.1: Timing Adjustable <https://www.w3.org/WAI/WCAG22/quickref/#timing-adjustable>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-pause-stop-hide:
        
      `2.2.2: Pause, Stop, Hide <https://www.w3.org/WAI/WCAG22/quickref/#pause-stop-hide>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-three-flashes-or-below-threshold:
        
      `2.3.1: Three Flashes or Below Threshold <https://www.w3.org/WAI/WCAG22/quickref/#three-flashes-or-below-threshold>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-bypass-blocks:
        
      `2.4.1: Bypass Blocks <https://www.w3.org/WAI/WCAG22/quickref/#bypass-blocks>`__ (Level A)
    - Supports
    - ARIA landmarks are used to identify the header, navigation, and main sections of the page.
      Each section in the main content has a header identifying it.
  -
    - .. _vpat-page-titled:
        
      `2.4.2: Page Titled <https://www.w3.org/WAI/WCAG22/quickref/#page-titled>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-focus-order:
        
      `2.4.3: Focus Order <https://www.w3.org/WAI/WCAG22/quickref/#focus-order>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-link-purpose-in-context:
        
      `2.4.4: Link Purpose (In Context) <https://www.w3.org/WAI/WCAG22/quickref/#link-purpose-in-context>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-pointer-gestures:
        
      `2.5.1: Pointer Gestures <https://www.w3.org/WAI/WCAG22/quickref/#pointer-gestures>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-pointer-cancellation:
        
      `2.5.2: Pointer Cancellation <https://www.w3.org/WAI/WCAG22/quickref/#pointer-cancellation>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-label-in-name:
        
      `2.5.3: Label in Name <https://www.w3.org/WAI/WCAG22/quickref/#label-in-name>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-motion-actuation:
        
      `2.5.4: Motion Actuation <https://www.w3.org/WAI/WCAG22/quickref/#motion-actuation>`__ (Level A)
    - Not Applicable
    - 
  -
    - .. _vpat-language-of-page:
        
      `3.1.1: Language of Page <https://www.w3.org/WAI/WCAG22/quickref/#language-of-page>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-on-focus:
        
      `3.2.1: On Focus <https://www.w3.org/WAI/WCAG22/quickref/#on-focus>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-on-input:
        
      `3.2.2: On Input <https://www.w3.org/WAI/WCAG22/quickref/#on-input>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-consistent-help:
        
      `3.2.6: Consistent Help <https://www.w3.org/WAI/WCAG22/quickref/#consistent-help>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-error-identification:
        
      `3.3.1: Error Identification <https://www.w3.org/WAI/WCAG22/quickref/#error-identification>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-labels-or-instructions:
        
      `3.3.2: Labels or Instructions <https://www.w3.org/WAI/WCAG22/quickref/#labels-or-instructions>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-redundant-entry:
        
      `3.3.7: Redundant Entry <https://www.w3.org/WAI/WCAG22/quickref/#redundant-entry>`__ (Level A)
    - Supports
    - 
  -
    - .. _vpat-name-role-value:
        
      `4.1.2: Name, Role, Value <https://www.w3.org/WAI/WCAG22/quickref/#name-role-value>`__ (Level A)
    - Supports
    - 

Table 1: Success Criteria, Level AA
***********************************

.. list-table::
  :header-rows: 1

  - 

     - Criteria
     - Conformance Level
     - Remarks and Explanations
  -
    - .. _vpat-captions-live:
        
      `1.2.4: Captions (Live) <https://www.w3.org/WAI/WCAG22/quickref/#captions-live>`__ (Level AA)
    - Not Applicable
    - 
  -
    - .. _vpat-audio-description-prerecorded:
        
      `1.2.5: Audio Description (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#audio-description-prerecorded>`__ (Level AA)
    - Not Applicable
    - 
  -
    - .. _vpat-orientation:
        
      `1.3.4: Orientation <https://www.w3.org/WAI/WCAG22/quickref/#orientation>`__ (Level AA)
    - Supports
    - Elements are adaptive, though some tables require horizontal scrolling when small-width.
  -
    - .. _vpat-identify-input-purpose:
        
      `1.3.5: Identify Input Purpose <https://www.w3.org/WAI/WCAG22/quickref/#identify-input-purpose>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-reflow:
        
      `1.4.10: Reflow <https://www.w3.org/WAI/WCAG22/quickref/#reflow>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-non-text-contrast:
        
      `1.4.11: Non-text Contrast <https://www.w3.org/WAI/WCAG22/quickref/#non-text-contrast>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-text-spacing:
        
      `1.4.12: Text Spacing <https://www.w3.org/WAI/WCAG22/quickref/#text-spacing>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-content-on-hover-or-focus:
        
      `1.4.13: Content on Hover or Focus <https://www.w3.org/WAI/WCAG22/quickref/#content-on-hover-or-focus>`__ (Level AA)
    - Not Applicable
    - No content is made visible just by pointer hover or keyboard focus.
  -
    - .. _vpat-contrast-minimum:
        
      `1.4.3: Contrast (Minimum) <https://www.w3.org/WAI/WCAG22/quickref/#contrast-minimum>`__ (Level AA)
    - Supports
    - Colours have been deliberately picked whilst testing against WCAG and APCA contrast guidelines. We attempt to meet the preferred contrast of 7.0 where feasible.       
      Some colours have a lower, but still compliant, contrast compared to the background where distinguishing between different adjacent text colours (for example, for the 'danger' and 'warning' colours) necessitated it.
  -
    - .. _vpat-resize-text:
        
      `1.4.4: Resize text <https://www.w3.org/WAI/WCAG22/quickref/#resize-text>`__ (Level AA)
    - Supports
    - Page layout is dynamic and functions well with 200% zoom.
  -
    - .. _vpat-images-of-text:
        
      `1.4.5: Images of Text <https://www.w3.org/WAI/WCAG22/quickref/#images-of-text>`__ (Level AA)
    - Supports
    - No images of text are used, text in generated graphs is still tagged as text.
  -
    - .. _vpat-focus-not-obscured-minimum:
        
      `2.4.11: Focus Not Obscured (Minimum) <https://www.w3.org/WAI/WCAG22/quickref/#focus-not-obscured-minimum>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-multiple-ways:
        
      `2.4.5: Multiple Ways <https://www.w3.org/WAI/WCAG22/quickref/#multiple-ways>`__ (Level AA)
    - Supports
    - In the admin interface, you can navigate to a resource either by searching for it or by clicking through the consumer and context levels.

      Within a resource, instructors can find a particular attempt either by searching for the student's name or by reading through the table of attempts.
  -
    - .. _vpat-headings-and-labels:
        
      `2.4.6: Headings and Labels <https://www.w3.org/WAI/WCAG22/quickref/#headings-and-labels>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-focus-visible:
        
      `2.4.7: Focus Visible <https://www.w3.org/WAI/WCAG22/quickref/#focus-visible>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-dragging-movements:
        
      `2.5.7: Dragging Movements <https://www.w3.org/WAI/WCAG22/quickref/#dragging-movements>`__ (Level AA)
    - Not Applicable
    - There are no dragging interactions.
  -
    - .. _vpat-target-size-minimum:
        
      `2.5.8: Target Size (Minimum) <https://www.w3.org/WAI/WCAG22/quickref/#target-size-minimum>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-language-of-parts:
        
      `3.1.2: Language of Parts <https://www.w3.org/WAI/WCAG22/quickref/#language-of-parts>`__ (Level AA)
    - Not Applicable
    - Sub-parts do not have different languages to the main language of the page.
  -
    - .. _vpat-consistent-navigation:
        
      `3.2.3: Consistent Navigation <https://www.w3.org/WAI/WCAG22/quickref/#consistent-navigation>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-consistent-identification:
        
      `3.2.4: Consistent Identification <https://www.w3.org/WAI/WCAG22/quickref/#consistent-identification>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-error-suggestion:
        
      `3.3.3: Error Suggestion <https://www.w3.org/WAI/WCAG22/quickref/#error-suggestion>`__ (Level AA)
    - Supports
    - 
  -
    - .. _vpat-error-prevention-legal-financial-data:
        
      `3.3.4: Error Prevention (Legal, Financial, Data) <https://www.w3.org/WAI/WCAG22/quickref/#error-prevention-legal-financial-data>`__ (Level AA)
    - Supports
    - The user is asked to confirm before deleting anything. Deleted consumers and attempts are kept in the database but marked as 'deleted' and can be restored by administrators.
  -
    - .. _vpat-accessible-authentication-minimum:
        
      `3.3.8: Accessible Authentication (Minimum) <https://www.w3.org/WAI/WCAG22/quickref/#accessible-authentication-minimum>`__ (Level AA)
    - Supports
    - Authentication in LTI launches is handled automatically.

      Authentication for the admin interface requires a password, which can be filled by a password manager.
  -
    - .. _vpat-status-messages:
        
      `4.1.3: Status Messages <https://www.w3.org/WAI/WCAG22/quickref/#status-messages>`__ (Level AA)
    - Supports
    - 

Table 1: Success Criteria, Level AAA
************************************

.. list-table::
  :header-rows: 1

  - 

     - Criteria
     - Conformance Level
     - Remarks and Explanations
  -
    - .. _vpat-sign-language-prerecorded:
        
      `1.2.6: Sign Language (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#sign-language-prerecorded>`__ (Level AAA)
    - Not Applicable
    - 
  -
    - .. _vpat-extended-audio-description-prerecorded:
        
      `1.2.7: Extended Audio Description (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#extended-audio-description-prerecorded>`__ (Level AAA)
    - Not Applicable
    - 
  -
    - .. _vpat-media-alternative-prerecorded:
        
      `1.2.8: Media Alternative (Prerecorded) <https://www.w3.org/WAI/WCAG22/quickref/#media-alternative-prerecorded>`__ (Level AAA)
    - Not Applicable
    - 
  -
    - .. _vpat-audio-only-live:
        
      `1.2.9: Audio-only (Live) <https://www.w3.org/WAI/WCAG22/quickref/#audio-only-live>`__ (Level AAA)
    - Not Applicable
    - 
  -
    - .. _vpat-identify-purpose:
        
      `1.3.6: Identify Purpose <https://www.w3.org/WAI/WCAG22/quickref/#identify-purpose>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-contrast-enhanced:
        
      `1.4.6: Contrast (Enhanced) <https://www.w3.org/WAI/WCAG22/quickref/#contrast-enhanced>`__ (Level AAA)
    - Partially Supports
    - Colours differentiating between different types of text (success and danger for example) have a lower contrast ratio to the background, meeting the AA threshold, in the interest of them being distinguishable from each other.
      These colours are never used for more than a few words together.
  -
    - .. _vpat-low-or-no-background-audio:
        
      `1.4.7: Low or No Background Audio <https://www.w3.org/WAI/WCAG22/quickref/#low-or-no-background-audio>`__ (Level AAA)
    - Not Applicable
    - 
  -
    - .. _vpat-visual-presentation:
        
      `1.4.8: Visual Presentation <https://www.w3.org/WAI/WCAG22/quickref/#visual-presentation>`__ (Level AAA)
    - Partially Supports
    - The user can't select their own foreground and background colours, other than to switch to a dark colour scheme.
  -
    - .. _vpat-images-of-text-no-exception:
        
      `1.4.9: Images of Text (No Exception) <https://www.w3.org/WAI/WCAG22/quickref/#images-of-text-no-exception>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-keyboard-no-exception:
        
      `2.1.3: Keyboard (No Exception) <https://www.w3.org/WAI/WCAG22/quickref/#keyboard-no-exception>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-no-timing:
        
      `2.2.3: No Timing <https://www.w3.org/WAI/WCAG22/quickref/#no-timing>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-interruptions:
        
      `2.2.4: Interruptions <https://www.w3.org/WAI/WCAG22/quickref/#interruptions>`__ (Level AAA)
    - Not Applicable
    - 
  -
    - .. _vpat-re-authenticating:
        
      `2.2.5: Re-authenticating <https://www.w3.org/WAI/WCAG22/quickref/#re-authenticating>`__ (Level AAA)
    - Supports
    - Authenticated sessions don't expire.
  -
    - .. _vpat-timeouts:
        
      `2.2.6: Timeouts <https://www.w3.org/WAI/WCAG22/quickref/#timeouts>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-three-flashes:
        
      `2.3.2: Three Flashes <https://www.w3.org/WAI/WCAG22/quickref/#three-flashes>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-animation-from-interactions:
        
      `2.3.3: Animation from Interactions <https://www.w3.org/WAI/WCAG22/quickref/#animation-from-interactions>`__ (Level AAA)
    - Not Applicable
    - There are no animations triggered by interactions.
  -
    - .. _vpat-section-headings:
        
      `2.4.10: Section Headings <https://www.w3.org/WAI/WCAG22/quickref/#section-headings>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-focus-not-obscured-enhanced:
        
      `2.4.12: Focus Not Obscured (Enhanced) <https://www.w3.org/WAI/WCAG22/quickref/#focus-not-obscured-enhanced>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-focus-appearance:
        
      `2.4.13: Focus Appearance <https://www.w3.org/WAI/WCAG22/quickref/#focus-appearance>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-location:
        
      `2.4.8: Location <https://www.w3.org/WAI/WCAG22/quickref/#location>`__ (Level AAA)
    - Supports
    - The current location is highlighted in the header and marked up as the ARIA current page.
  -
    - .. _vpat-link-purpose-link-only:
        
      `2.4.9: Link Purpose (Link Only) <https://www.w3.org/WAI/WCAG22/quickref/#link-purpose-link-only>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-target-size:
        
      `2.5.5: Target Size <https://www.w3.org/WAI/WCAG22/quickref/#target-size>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-concurrent-input-mechanisms:
        
      `2.5.6: Concurrent Input Mechanisms <https://www.w3.org/WAI/WCAG22/quickref/#concurrent-input-mechanisms>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-unusual-words:
        
      `3.1.3: Unusual Words <https://www.w3.org/WAI/WCAG22/quickref/#unusual-words>`__ (Level AAA)
    - Supports
    - Jargon terms are explained in the glossary page of the documentation.
  -
    - .. _vpat-abbreviations:
        
      `3.1.4: Abbreviations <https://www.w3.org/WAI/WCAG22/quickref/#abbreviations>`__ (Level AAA)
    - Supports
    - Abbreviations are explained in the glossary in the documentation.
  -
    - .. _vpat-reading-level:
        
      `3.1.5: Reading Level <https://www.w3.org/WAI/WCAG22/quickref/#reading-level>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-pronunciation:
        
      `3.1.6: Pronunciation <https://www.w3.org/WAI/WCAG22/quickref/#pronunciation>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-change-on-request:
        
      `3.2.5: Change on Request <https://www.w3.org/WAI/WCAG22/quickref/#change-on-request>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-help:
        
      `3.3.5: Help <https://www.w3.org/WAI/WCAG22/quickref/#help>`__ (Level AAA)
    - Supports
    - Every page in the management interface has a link to the corresponding part of the documentation, labelled "Help with this page".
  -
    - .. _vpat-error-prevention-all:
        
      `3.3.6: Error Prevention (All) <https://www.w3.org/WAI/WCAG22/quickref/#error-prevention-all>`__ (Level AAA)
    - Supports
    - 
  -
    - .. _vpat-accessible-authentication-enhanced:
        
      `3.3.9: Accessible Authentication (Enhanced) <https://www.w3.org/WAI/WCAG22/quickref/#accessible-authentication-enhanced>`__ (Level AAA)
    - Supports
    - 

