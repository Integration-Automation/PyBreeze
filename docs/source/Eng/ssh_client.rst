SSH Client
==========

PyBreeze includes a built-in SSH client for connecting to remote servers.
It can be opened from **Tools > SSH Client Tab** or **Tools > SSH Client Dock**.

Overview
--------

The SSH client provides three main components arranged in a horizontal splitter:

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
     - The hostname or IP address of the remote server.
   * - **Port**
     - The SSH port number (default: 22).
   * - **Username**
     - Your SSH username.
   * - **Password / Key**
     - Authentication credentials. Supports password-based and key-based authentication.

After entering your credentials, click **Connect** to establish the SSH session.

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
   * - **Create Folder**
     - Creates a new directory on the remote server.
   * - **Rename**
     - Renames the selected file or directory.
   * - **Delete**
     - Deletes the selected file or directory from the remote server.
   * - **Download**
     - Downloads the selected file to your local machine.
   * - **Upload**
     - Uploads a local file to the current remote directory.

SSH Command Terminal
--------------------

The command widget provides an interactive terminal for executing commands
on the remote server.

- Type commands and press Enter to execute
- Output is displayed in real-time
- Supports standard shell operations
- Command history is maintained during the session

Usage Tips
----------

- Use the **Tab** mode to keep SSH alongside your code editor tabs
- Use the **Dock** mode to position the SSH terminal on one side while coding
- The file browser supports drag-and-drop for uploads
- You can have multiple SSH sessions open simultaneously in separate tabs/docks
