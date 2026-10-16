# 🐾 SnoopyOS-image
<img width="1536" height="924" alt="ChatGPT Image Oct 16, 2026, 05_01_24 PM" src="https://github.com/user-attachments/assets/a91c68e9-87fd-4b83-a589-9b4b1c6f4aae" />
**SnoopyOS-image** is a repository dedicated to the development, hosting, and maintenance of pre-configured images and custom environments for **SnoopyOS**. It provides compatibility for a diverse range of hardware scenarios, drawing from projects within enthusiast communities.

The goal of this project is to provide a clean, optimized, and deployment-ready image, reducing the time spent on post-installation configuration and the fine-tuning of kexts/drivers.

---

## 🛠️ Repository Contents

*   **System Images:** Image files (`.img`, `.iso`, or raw) optimized for quick booting and installation.
*   **EFI Folders / Bootloaders:** Configuration files structured to ensure initial compatibility with various chipsets and processors.
*   **Patches and Tweaks:** Post-installation utility scripts for performance optimization, power management, and graphics acceleration.

---

## 🚀 How to Use the Image

### Prerequisites
*   A flash drive or external storage device with a minimum capacity of **16GB** (recommended).
*   An image-flashing tool (such as **BalenaEtcher**, **Rufus** in DD mode, or the `dd` utility via the terminal).

### Installation (via Linux/macOS CLI)

1.  **Download the latest version** from the [Releases](https://github.com) tab.
2.  **Identify your target drive** (e.g., `/dev/sdX` or `/dev/diskX`). 3.  **Write the image to the device** by executing the command below (replace the image path and drive identifier with your actual details):

```bash
sudo dd if=SnoopyOS-v1.0.img of=/dev/sdX bs=4M status=progress && sync
```

---

## ⚙️ Recommended BIOS Settings

To ensure the system boots without crashes (*kernel panics*), please configure your motherboard as follows:

| Setting | Recommended Status |
| :--- | :--- |
| **SATA Mode** | AHCI |
| **Secure Boot** | Disabled |
| **Fast Boot** | Disabled |
| **VT-d** | Enabled (or Disabled, depending on the applied patches) |
| **Above 4G Decoding** | Enabled |

---

## 📂 Repository Structure

```text
SnoopyOS-image/
├── EFI/                # Bootloader files (OpenCore/Clover/GRUB)
├── Patches/            # ACPI fixes, kernel patches, and essential Kexts
├── Scripts/            # Automated tools for partition mounting
└── README.md           # Main project documentation
```

---

## 🤝 How to Contribute

If you have tested the image on specific hardware and would like to share your feedback or submit fixes to the file structure:

1. **Fork** this repository.
2. Create a branch for your changes (`git checkout -b feature/efi-improvement`).
3. Submit a **Pull Request**, providing detailed information about the hardware used in your tests (CPU, GPU, Motherboard).

---

## 📄 Legal Notes and License
This project is intended strictly for educational purposes and the study of operating system architecture. All trademarks belong to their respective owners. Distributed under the **Apache 2.0** license.

This project is intended strictly for educational purposes and the study of operating system architecture. All trademarks belong to their respective owners. Distributed under the **MIT** license.
