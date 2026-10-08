SSH Client
==========

PyBreeze includes a built-in SSH client for connecting to remote servers.
It can be opened from **Tools > SSH > SSH Client Tab** or **Dock > SSH > SSH Client Dock**.

Overview
--------

The SSH client shows the login widget at the top, above a horizontal splitter holding
the file tree and the command widget:

1. **Login Widget** (top) -- Connection settings
2. **File Tree** (left, ~30% width) -- Remote file browser
3. **Command Widget** (right, ~70% width) -- Interactive SSH terminal

Login Widget
------------

The login widget provides fields for SSH connection:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Field
     - Description
   * - **Host**
     - The host name or IP address of the remote server.
   * - **Port**
     - The SSH port number (default: 22).
   * - **User**
     - Your SSH user name.
   * - **Use key auth**
     - Tick for key-based authentication (choosing a key with **Browse...** ticks it).
   * - **Key** / **Browse...**
     - Path to the private key: an RSA, Ed25519 or ECDSA key in OpenSSH or PEM format,
       PKCS#8 included (**Browse...** starts in ``~/.ssh``). A PuTTY ``.ppk`` key must first
       be exported from PuTTYgen as an OpenSSH key; the error message says how.
   * - **Password**
     - The password; with key authentication it reads **Passphrase** and takes the key's
       passphrase.

After entering your credentials, click **Connect** (or press Enter in any field) to establish
the SSH session. An unknown host key is not accepted silently: its SHA256 fingerprint is shown
for confirmation on the first connection and kept in ``~/.pybreeze/ssh_known_hosts``. Hosts in
``~/.ssh/known_hosts`` are trusted as well. A host trusted before that shows another key is
refused without a question: someone may be intercepting the connection. The message gives both
SHA256 fingerprints and the file holding the trusted one; if the server's key was changed on
purpose, remove the host's line from that file and connect again.

Remote File Browser
-------------------

Once connected, the file tree displays the remote server's file system.

Context Menu Actions
^^^^^^^^^^^^^^^^^^^^

Right-click on any file or directory in the file tree to access:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Action
     - Description
   * - **Refresh**
     - Reloads the current directory listing from the remote server.
   * - **Create folder**
     - Creates a new directory on the remote server.
   * - **Rename**
     - Renames the selected file or directory (also **F2** while the tree has the focus).
   * - **Delete**
     - Deletes the selected file or directory from the remote server after a confirmation
       (No is the default; also the **Delete** key while the tree has the focus). SFTP removes
       only an empty folder.
   * - **Download**
     - Downloads the selected file to your local machine.
   * - **Upload to this folder**
     - Uploads a local file into the folder right-clicked (or the folder holding the file
       right-clicked), asking before it replaces a file on the server.
   * - **Cancel the transfer**
     - Shown while an upload or download runs; cancels it.

Every request runs in the background, so a stalled link does not freeze the IDE, and both
directions write to a temporary file first, so a dropped link leaves the old copy whole.

SSH Command Terminal
--------------------

The command widget provides an interactive terminal for executing commands
on the remote server.

- Type commands and press Enter to execute; Enter on an empty line reaches the shell too
- Output is displayed in real time, with ANSI colours, in a fixed-pitch font; the shell is
  told the terminal's width and height as the view is resized
- **Up** and **Down** bring back earlier commands
- **Interrupt**, or Ctrl+C in the command line with nothing selected, stops what runs in the shell
- ``clear`` and ``reset`` wipe the view
- The view shows output line by line, so programs that draw on the whole screen by moving the
  cursor, such as ``vim`` or ``htop``, come out garbled

Usage Tips
----------

- Use the **Tab** mode to keep SSH alongside your code editor tabs
- Use the **Dock** mode to position the SSH terminal on one side while coding
- Upload and download from the file tree's right-click menu; F2 renames and Delete deletes
  the entry in focus
- You can have multiple SSH sessions open simultaneously in separate tabs/docks
