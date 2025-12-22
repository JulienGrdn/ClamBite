# ClamBite

**ClamBite** is a modern, lightweight graphical user interface for ClamAV, built with Python, GTK4, and LibAdwaita. It provides a user-friendly way to scan files and folders, manage virus definitions, and view scan history on Linux desktops.

![ClamBite Logo](clambite.svg)

## Features

*   **Modern UI**: Built with LibAdwaita for a native GNOME look and feel.
*   **Compact Dashboard**: Access key actions (Scan File, Scan Folder, Database, History).
*   **Smart Updates**: Checks database freshness before scanning. If the database is outdated (>5 days), it prompts you to update with a countdown timer.
*   **Detailed Reporting**: View formatted scan results with metrics (Time, Engine Version, Data Scanned).
*   **History**: distinct views for past Scans and Database Updates.
*   **User-Mode Operation**: Stores logs and databases in `~/.config/ClamBite`, allowing operation without root privileges.

## Requirements

*   Python 3.8+
*   GTK4
*   LibAdwaita
*   ClamAV (including `clamscan` and `freshclam`)
*   `python3-gobject`

## Installation

### Fedora / RPM-based Systems (COPR)

*Coming soon.*

### Manual Installation

1.  **Install Dependencies**:
    ```bash
    # Fedora
    sudo dnf install python3 python3-gobject gtk4 libadwaita clamav clamav-freshclam

    # Ubuntu/Debian
    sudo apt install python3 python3-gi libgtk-4-1 libadwaita-1-0 clamav clamav-freshclam
    ```

2.  **Clone the Repository**:
    ```bash
    git clone https://github.com/JulienGrdn/ClamBite.git
    cd clambite
    ```

3.  **Run**:
    ```bash
    python3 main.py
    ```

## Usage

1.  **Dashboard**: Use the buttons to initiate a scan or check database status.
2.  **Scanning**: Select a file or folder. ClamBite will check if your definitions are fresh.
3.  **Database**: Click "Database" to view the last update log or force a manual update.
4.  **Logs**: Review past scan results and update history.

## Configuration

ClamBite stores its data in your user configuration directory:
*   **Path**: `~/.config/ClamBite/`
    *   `logs/`: Scan and update logs.
    *   `clamav-db/`: Local virus definitions.

## License

MIT