# Sistemi për Menaxhimin e Ankesave dhe Kërkesave të Klientit

**Universiteti:** Universiteti “Ukshin Hoti” – Prizren  
**Fakulteti:** Fakulteti i Shkencave Kompjuterike  
**Programi:** Dizajnimi i Softuerëve  
**Lënda:** Projekt  
**Studenti/ja:** Shkurte Bytyqi (ID: 240329075)  
**Profesori:** Endrit Fetahu  
**Data:** Tetor 2026  

---

## 1. Analiza e Problemit dhe Konteksti

### 1.1 Problemi që zgjidh projekti
Në shumë organizata, kompani dhe institucione, menaxhimi i ankesave dhe kërkesave të klientëve bëhet përmes formave jo të strukturuara (si email-et, telefonatat ose shënimet fizike). Kjo mënyrë sjell disa probleme kryesore:
* Humbjen ose vonesën në trajtimin e ankesave.
* Mungesën e transparencës për klientin lidhur me statusin e kërkesës së tij.
* Pamundësinë e stafit drejtues për të matur performancën e zgjidhjes së problemeve.

Sistemi për Menaxhimin e Ankesave dhe Kërkesave të Klientëve zgjidh këtë problem duke ofruar një platformë të centralizuar digjitale ku çdo ankesë regjistrohet, merr një ID unike, i caktohet një status i caktuar dhe ndiqet hap pas hapi deri në zgjidhjen përfundimtare.

### 1.2 Përdoruesit e synuar
Sistemi parashikon dy role kryesore përdoruesish:
* **Klienti (Përdoruesi i thjeshtë):** Mund të regjistrojë ankesa/kërkesa të reja, të bashkëngjisë detaje relevante, si dhe të përcjellë historikun dhe ecurinë e tyre në kohë reale.
* **Administratori / Stafi Trajtues:** Ka qasje në panelin e menaxhimit për të shqyrtuar ankesat e arritura, për t'i ndryshuar statusin, për t'u kthyer përgjigje klientëve dhe për të analizuar statistikat e përgjithshme.

---

## 2. Kërkesat e Sistemit (System Requirements)

### 2.1 Kërkesat Funksionale (Functional Requirements)
* **FR-01 (Autentikimi dhe Autorizimi):** Përdoruesi mund të krijojë një llogari të re (Register) dhe të kyçet në sistem (Login) përmes email-it dhe fjalëkalimit. Sistemi e ridrejton përdoruesin në ndërfaqen përkatëse në bazë të rolit të tij (Klient apo Administrator).
* **FR-02 (Regjistrimi i Ankesës):** Klienti i autentikuar mund të krijojë një ankesë të re duke plotësuar titullin, kategorinë (p.sh. Shërbim, Teknike, Financiare), përshkrimin e detajuar dhe nivelin e urgjencës.
* **FR-03 (Menaxhimi i Statusit të Ankesës):** Administratori mund të ndryshojë statusin e ankesës (Në pritje, Në shqyrtim, Zgjidhur, Refuzuar) dhe të vendosë një komentin/përgjigje zyrtare për klientin.
* **FR-04 (Filtrimi dhe Kërkimi):** Klienti dhe administratori mund të filtrojnë ankesat sipas statusit, kategorisë ose datës së krijimit.
* **FR-05 (Historiku i Ankesave):** Klienti mund të shohë një listë me të gjitha ankesat e tij të mëparshme dhe statusin aktual të secilës prej tyre.

### 2.2 Kërkesat Jofunksionale (Non-Functional Requirements)
* **NFR-01 (Siguria e Fjalëkalimeve):** Fjalëkalimet e përdoruesve nuk ruhen kurrë në tekst të hapur (plain text); ato ruhen të hash-uara duke përdorur algoritmin Bcrypt.
* **NFR-02 (Kontrolli i Qasjes):** Endpoint-et private dhe faqet menaxhuese kërkojnë autentikim dhe autorizim; një përdorues pa role administrative refuzohet nga qasja në panelin e administratorit.
* **NFR-03 (Validimi i të Dhënave):** Çdo input validohet si në frontend (UI validation) ashtu edhe në backend para se të ruhet në databazë për të parandaluar të dhënat e pavlefshme ose sulmet si SQL Injection dhe XSS.
* **NFR-04 (Përshtatshmëria - Responsive Design):** Ndërfaqja e përdoruesit (UI) është e optimizuar për t'u përdorur si në ekranet e kompjuterëve desktop ashtu edhe në pajisjet mobile.

---

## 3. Dizajni Teknik dhe Arkitektura e Sistemit

### 3.1 Arkitektura e Aplikacionit
Sistemi do të ndërtohet me arkitekturë standarde me 3 shtresa (3-tier architecture):
* **Frontend (Shtresa e Prezantimit):** Zhvillohet me HTML5, CSS3, JavaScript dhe Bootstrap për të garantuar një ndërfaqe moderne, dinamike dhe responsive.
* **Backend (Shtresa e Logjikës së Biznesit):** Zhvillohet me PHP / Python / Node.js, i cili përpunon kërkesat HTTP, bën validimin e të dhënave, menaxhon session-et/token-at e autentikimit dhe komunikon me databazën.
* **Database (Shtresa e të Dhënave):** Baza e të dhënave relacionale MySQL / MariaDB për ruajtjen e strukturuar dhe të sigurt të përdoruesve, ankesave dhe kategorive.

---

## 4. Modeli Fillestar i Databazës

### 4.1 Entitetet dhe Strukturat e Tabelave
* **Tabela 1: `users` (Përdoruesit)**
  * `id`: INT (Primary Key, Auto Increment) - Identifikuesi unik i përdoruesit
  * `full_name`: VARCHAR(100) (NOT NULL) - Emri dhe mbiemri
  * `email`: VARCHAR(120) (UNIQUE, NOT NULL) - Adresa e email-it për login
  * `password`: VARCHAR(255) (NOT NULL) - Hash-i i fjalëkalimit
  * `role`: ENUM ('client', 'admin'), DEFAULT 'client' - Roli i përdoruesit në sistem
  * `created_at`: TIMESTAMP (DEFAULT CURRENT_TIMESTAMP) - Data e regjistrimit

* **Tabela 2: `categories` (Kategoritë e Ankesave)**
  * `id`: INT (Primary Key, Auto Increment) - Identifikuesi unik i kategorisë
  * `name`: VARCHAR(50) (NOT NULL, UNIQUE) - Emri i kategorisë (p.sh. Teknike, Financiare)
  * `description`: TEXT (NULLABLE) - Përshkrim i shkurtër i kategorisë

* **Tabela 3: `complaints` (Ankesat / Kërkesat)**
  * `id`: INT (Primary Key, Auto Increment) - Identifikuesi unik i ankesës
  * `user_id`: INT (Foreign Key references users.id) - Përdoruesi që ka paraqitur ankesën
  * `category_id`: INT (Foreign Key references categories.id) - Kategoria ku bën pjesë ankesa
  * `title`: VARCHAR(150) (NOT NULL) - Titulli i ankesës
  * `description`: TEXT (NOT NULL) - Përshkrimi i hollësishëm i problemit
  * `status`: ENUM ('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar'), DEFAULT 'Në pritje' - Statusi aktual i trajtimit
  * `priority`: ENUM ('E ulët', 'Mesatare', 'E lartë'), DEFAULT 'Mesatare' - Niveli i urgjencës së ankesës
  * `admin_response`: TEXT (NULLABLE) - Përgjigja ose shënimi zyrtar
  * `created_at`: TIMESTAMP (DEFAULT CURRENT_TIMESTAMP) - Data e krijimit
  * `updated_at`: TIMESTAMP (DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) - Data e përditësimit të fundit

### 4.2 Relacionet Ndërmjet Tabelave
* **`users` -> `complaints` (Relacion 1-me-Shumë / 1:N):** Një përdorues (klient) mund të parashtrojë shumë ankesa, por çdo ankesë i përket vetëm një përdoruesi të caktuar (`user_id`).
* **`categories` -> `complaints` (Relacion 1-me-Shumë / 1:N):** Një kategori mund të përmbajë shumë ankesa, por çdo ankesë klasifikohet nën një kategori të vetme (`category_id`).
