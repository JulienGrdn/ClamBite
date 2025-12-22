Name:           clambite
Version:        1.0
Release:        1%{?dist}
Summary:        A modern ClamAV GUI for AV scans, using GTK4 and LibAdwaita

License:        MIT
URL:            https://github.com/JulienGrdn/ClamBite
Source0:        %{url}/archive/main.tar.gz

BuildArch:      noarch

# Core dependencies
Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       hicolor-icon-theme

# Application specific dependencies
Requires:       clamav
Requires:       clamav-freshclam

%description
ClamBite is a user-friendly graphical interface for ClamAV scan.
It features a modern dashboard, database update logic, and scan reporting. 
Designed for GNOME and GTK4 desktops.

%prep
%autosetup -n ClamBite-main

%build
# Nothing to build for pure python scripts

%install
# 1. Create directory structure
mkdir -p %{buildroot}%{_datadir}/%{name}
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p ~/.config/clambite
mkdir -p ~/.config/clambite/clam-db
mkdir -p ~/.config/clambite/clam-db/db
mkdir -p ~/.config/clambite/logs


# 2. Install Python source files to /usr/share/clambite/
install -m 644 clambite.py %{buildroot}%{_datadir}/%{name}/
install -m 644 ui.py %{buildroot}%{_datadir}/%{name}/
install -m 644 backend.py %{buildroot}%{_datadir}/%{name}/
install -m 644 parsers.py %{buildroot}%{_datadir}/%{name}/

# 3. Install the icon to the standard system path
# (Ensure your source repository has a 'clambite.svg')
install -m 644 clambite.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/clambite.svg

# 4. Create executable wrapper in /usr/bin/
cat > %{buildroot}%{_bindir}/%{name} <<EOF
#!/bin/sh
exec python3 %{_datadir}/%{name}/clambite.py "\$@"
EOF
chmod +x %{buildroot}%{_bindir}/%{name}

# 5. Create Desktop Entry
cat > %{buildroot}%{_datadir}/applications/%{name}.desktop <<EOF
[Desktop Entry]
Name=ClamBite
Comment=Modern ClamAV GUI Scanner
Exec=clambite
Icon=clambite
Terminal=false
Type=Application
Categories=Utility;System;Security;GTK;ClamAV,clam,virus
StartupWMClass=com.github.JulienGrdn.ClamBite
StartupNotify=true
EOF

%files
%license LICENSE
# %doc README.md
%{_bindir}/%{name}
%{_datadir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%changelog
* Mon Dec 22 2025 JulienGrdn - 1.0-1
- Initial package release for Fedora
