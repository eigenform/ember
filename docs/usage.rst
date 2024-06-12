Using this Repository
=====================

This build environment uses `PDM <https://pdm-project.org>`_ in an attempt to 
make managing dependencies on `Amaranth <https://github.com/amaranth-lang>`_ 
somewhat simpler. 

Setup (Arch Linux)
-------------------

.. code-block:: bash

    # Install pipx and pdm
    $ sudo pacman -S python-pipx
    $ pipx install pdm

    # Clone this repository and install dependencies
    $ git clone https://github.com/eigenform/ember && cd ember
    $ pdm install

Build Scripts
-------------

You can get a list of all available build scripts like this:

.. code-block:: bash

    # Get the list of scripts used for testing/building the project
    $ pdm run --list

At this point in the project, we're really only concerned with running tests 
in simulation: 

.. code-block:: bash

    # Run unit tests
    $ pdm test-module

    # Run behavioral tests
    $ pdm test-pipeline

    # Run all tests
    $ pdm test

