.. _editorlink:

Editor links
============

:term:`Editor links <Editor link>` form a connection between the Numbas LTI tool provider and an instance of the Numbas editor, allowing instructors to select exams from a list inside the LTI tool, rather than downloading an exam package to their own computer and then uploading it to the LTI tool.

The `public Numbas editor hosted by mathcentre <https://numbas.mathcentre.ac.uk>`_ provides a wealth of ready-made exams on a variety of subjects.

.. _add-editor-link:

Creating an editor link
***********************

From the :ref:`admin interface <admin>`, click on the :guilabel:`Editor links` button at the top of the screen.

Click on the :guilabel:`Connect to a Numbas editor` button.
In the :guilabel:`Base URL of the editor` field, enter the address of the Numbas editor.

The address of the public editor hosted by mathcentre is::

    https://numbas.mathcentre.ac.uk

Once you've created an editor link, you can select the :ref:`projects <numbas:projects>` from the editor that you want to use.

Only projects which are :ref:`marked visible to non-members <numbas:public-project>` are available.
This is because the editor link has no authentication mechanism, and linked projects are available to all :ref:`consumers <consumer>`.

Once you have selected some projects, published exams from those projects will be available for instructors to pick on the :ref:`new Numbas activity <create-resource>` screen.
