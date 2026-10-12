import os
os.environ["TK_SILENCE_DEPRECATION"] = "1"
import sys
import json
import sqlite3
import csv
import tkinter as tk
import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
from tkinter import messagebox, ttk

# --- CONFIGURATION GLOBALE ---
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(APP_DIR, "data")
DB_FILE = os.path.join(APP_DIR, "suivi_atelier.db")
CONFIG_FILE = os.path.join(APP_DIR, "config_poste.json")

def get_postes_disponibles():
    default_fallback = [
        "DEC1 - Découpe Numérique SEKTOR",
        "USI1 - Centre Usinage 1",
        "FAC1 - Ligne Façonnage 1",
        "TRE1 - Four Trempe",
        "EXP1 - Zone Expédition"
    ]
    try:
        if not os.path.exists(DB_FILE):
            return default_fallback
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT CodPost, DesPost FROM Postes")
        postes = [f"{row[0]} - {row[1]}" for row in cursor.fetchall()]
        conn.close()
        return postes if postes else default_fallback
    except Exception:
        return default_fallback

class ConfigDialog(ctk.CTkToplevel):
    def __init__(self, parent, is_cancellable=False):
        super().__init__(parent)
        self.is_cancellable = is_cancellable
        self.title("Configuration du Poste")
        self.geometry("520x280")
        self.configure(fg_color="#0B1120")
        self.poste_choisi = tk.StringVar()
        self.result = None
        
        self.grab_set()
        
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        card = ctk.CTkFrame(self, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(card, text="⚙️ CONFIGURATION DU POSTE", 
                     font=("Segoe UI", 14, "bold"), text_color="#38BDF8").pack(pady=(20, 4))
        ctk.CTkLabel(card, text="Veuillez sélectionner votre poste de travail :", 
                     font=("Segoe UI", 12), text_color="#94A3B8").pack(pady=(0, 16))
        
        postes_list = get_postes_disponibles()
        self.cb = ctk.CTkComboBox(card, textvariable=self.poste_choisi, values=postes_list, 
                                  font=("Segoe UI", 13, "bold"), dropdown_font=("Segoe UI", 12),
                                  fg_color="#1E293B", border_color="#334155", text_color="#F8FAFC",
                                  button_color="#2563EB", button_hover_color="#1D4ED8",
                                  height=38, corner_radius=8, state="readonly")
        self.cb.pack(fill=tk.X, padx=30, pady=(0, 20))
        if postes_list:
            self.cb.set(postes_list[0])
            
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=30, pady=(0, 10))
        
        if self.is_cancellable:
            ctk.CTkButton(btn_frame, text="Annuler", font=("Segoe UI", 12, "bold"), 
                          fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", 
                          height=36, corner_radius=8, command=self.on_close).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
            
        ctk.CTkButton(btn_frame, text="Valider", font=("Segoe UI", 12, "bold"), 
                      fg_color="#2563EB", hover_color="#1D4ED8", text_color="#FFFFFF", 
                      height=36, corner_radius=8, command=self.on_validate).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(6 if self.is_cancellable else 0, 0))
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def on_validate(self):
        if self.poste_choisi.get():
            self.result = self.poste_choisi.get()
            self.destroy()
            
    def on_close(self):
        self.destroy()
        if not self.is_cancellable:
            sys.exit(0)

class AddOfDialog(ctk.CTkToplevel):
    def __init__(self, parent, db_conn, cde, default_qte=1, default_design="", default_obs="", lignes_sage=""):
        super().__init__(parent)
        self.title(f"Ajouter un Produit (OF) - Commande {cde}")
        self.geometry("740x720")
        self.configure(fg_color="#0B1120")
        self.db_conn = db_conn
        self.cde = cde
        self.lignes_sage = lignes_sage
        self.result = False
        
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        main_card = ctk.CTkFrame(self, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        main_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header Dialog
        header_dlg = ctk.CTkFrame(main_card, fg_color="transparent")
        header_dlg.pack(fill=tk.X, padx=20, pady=(16, 12))
        ctk.CTkLabel(header_dlg, text="📝 CRÉATION D'ORDRE DE FABRICATION (OF)", font=("Segoe UI", 15, "bold"), text_color="#38BDF8").pack(anchor="w")
        ctk.CTkLabel(header_dlg, text=f"Rattaché à la commande Sage : {cde}", font=("Segoe UI", 12), text_color="#94A3B8").pack(anchor="w")
        
        # Formulaire
        form_frame = ctk.CTkFrame(main_card, fg_color="transparent")
        form_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=4)
        
        form_frame.columnconfigure(0, weight=0)
        form_frame.columnconfigure(1, weight=1)
        
        # Produit
        ctk.CTkLabel(form_frame, text="Produit :", font=("Segoe UI", 12, "bold"), text_color="#94A3B8").grid(row=0, column=0, sticky="w", pady=8, padx=(0, 10))
        
        self.prod_var = tk.StringVar()
        self.cb_prod = ctk.CTkComboBox(form_frame, textvariable=self.prod_var, state="readonly", width=380, height=36,
                                      font=("Segoe UI", 12), fg_color="#1E293B", border_color="#334155", text_color="#F8FAFC",
                                      button_color="#2563EB", button_hover_color="#1D4ED8", corner_radius=8)
        self.cb_prod.grid(row=0, column=1, sticky="w", pady=8)
        self.cb_prod.bind("<<ComboboxSelected>>", self.on_prod_select)
        
        # Charger les produits
        self.produits_map = {}
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT RefProd, DesProd FROM Produits")
        for row in cursor.fetchall():
            display = f"{row[0]} - {row[1]}"
            self.produits_map[display] = (row[0], row[1])
        prod_values = list(self.produits_map.keys())
        self.cb_prod.configure(values=prod_values)
        
        # Designation
        ctk.CTkLabel(form_frame, text="Désignation :", font=("Segoe UI", 12, "bold"), text_color="#94A3B8").grid(row=1, column=0, sticky="w", pady=8, padx=(0, 10))
        self.design_var = tk.StringVar(value=default_design)
        ctk.CTkEntry(form_frame, textvariable=self.design_var, font=("Segoe UI", 12), width=380, height=36,
                     fg_color="#1E293B", border_color="#334155", text_color="#F8FAFC", corner_radius=8).grid(row=1, column=1, sticky="w", pady=8)
        
        # Observations
        ctk.CTkLabel(form_frame, text="Observations :", font=("Segoe UI", 12, "bold"), text_color="#94A3B8").grid(row=2, column=0, sticky="w", pady=8, padx=(0, 10))
        self.obs_var = tk.StringVar(value=default_obs)
        ctk.CTkEntry(form_frame, textvariable=self.obs_var, font=("Segoe UI", 12), width=380, height=36,
                     fg_color="#1E293B", border_color="#334155", text_color="#F8FAFC", corner_radius=8).grid(row=2, column=1, sticky="w", pady=8)
        
        # Quantite
        ctk.CTkLabel(form_frame, text="Quantité :", font=("Segoe UI", 12, "bold"), text_color="#94A3B8").grid(row=3, column=0, sticky="w", pady=8, padx=(0, 10))
        self.qte_var = tk.IntVar(value=default_qte)
        ctk.CTkEntry(form_frame, textvariable=self.qte_var, font=("Segoe UI", 12, "bold"), width=120, height=36,
                     fg_color="#1E293B", border_color="#334155", text_color="#F8FAFC", corner_radius=8).grid(row=3, column=1, sticky="w", pady=8)
        
        # Gamme Preview avec choix des postes
        ctk.CTkLabel(form_frame, text="⚙️ Gamme & Assignation des Postes :", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").grid(row=4, column=0, columnspan=2, sticky="w", pady=(14, 6))
        
        self.gamme_frame = ctk.CTkFrame(form_frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        self.gamme_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=4)
        self.gamme_vars = []

        # Boutons Footer
        self.btn_frame = ctk.CTkFrame(main_card, fg_color="transparent")
        self.btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=16)
        
        ctk.CTkButton(self.btn_frame, text="Annuler", font=("Segoe UI", 12, "bold"), 
                      fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", 
                      height=36, corner_radius=8, command=self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(self.btn_frame, text="➕ Créer l'OF", font=("Segoe UI", 12, "bold"), 
                      fg_color="#059669", hover_color="#047857", text_color="#FFFFFF", 
                      height=36, corner_radius=8, command=self.save).pack(side=tk.RIGHT, padx=8)
        
        self.transient(parent)
        self.grab_set()

    def on_prod_select(self, event=None):
        selection = self.prod_var.get()
        if selection in self.produits_map:
            ref, des = self.produits_map[selection]
            self.design_var.set(des)
            
            # Construire la gamme interactive
            for widget in self.gamme_frame.winfo_children():
                widget.destroy()
            self.gamme_vars = []
            
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT Gammes.Ordre, Gammes.CodeOp, Operations.LibelOp FROM Gammes LEFT JOIN Operations ON Gammes.CodeOp = Operations.RefOp WHERE RefProd = ? ORDER BY Ordre", (ref,))
            gammes = cursor.fetchall()
            
            if not gammes:
                ctk.CTkLabel(self.gamme_frame, text="Aucune gamme définie pour ce produit.", font=("Segoe UI", 12), text_color="#94A3B8").pack(pady=12)
                return
                
            for step in gammes:
                ordre, code_op, libel_op = step
                libel_op = libel_op if libel_op else "Opération sans libellé"
                
                row_frame = ctk.CTkFrame(self.gamme_frame, fg_color="transparent")
                row_frame.pack(fill=tk.X, padx=12, pady=6)
                
                var_check = tk.BooleanVar(value=False)
                
                # Chercher les postes compatibles
                cursor.execute("SELECT CodPost, DesPost FROM Postes WHERE RefOp = ?", (code_op,))
                postes_compatibles = ["Libre (N'importe lequel)"] + [f"{r[0]} - {r[1]}" for r in cursor.fetchall()]
                
                var_poste = tk.StringVar(value=postes_compatibles[0])
                cb_poste = ctk.CTkComboBox(row_frame, textvariable=var_poste, values=postes_compatibles, 
                                          state="disabled", width=220, height=32, corner_radius=6,
                                          font=("Segoe UI", 11), fg_color="#0F172A", border_color="#334155", text_color="#F8FAFC",
                                          button_color="#334155")
                
                def on_check_toggle(v=var_check, c=cb_poste):
                    if v.get():
                        c.configure(state="readonly")
                    else:
                        c.configure(state="disabled")
                        
                chk = ctk.CTkCheckBox(row_frame, text=libel_op, variable=var_check, command=on_check_toggle,
                                      fg_color="#2563EB", hover_color="#1D4ED8", text_color="#F8FAFC",
                                      font=("Segoe UI", 12, "bold"), width=220)
                chk.pack(side=tk.LEFT)
                cb_poste.pack(side=tk.LEFT, padx=10)
                
                self.gamme_vars.append({
                    'code_op': code_op, 
                    'var_check': var_check,
                    'var_poste': var_poste,
                    'libel': libel_op
                })
                
    def save(self):
        selection = self.prod_var.get()
        if not selection:
            messagebox.showerror("Erreur", "Veuillez sélectionner un produit.")
            return
        
        ref_prod = self.produits_map[selection][0]
        design = self.design_var.get().strip()
        obs = self.obs_var.get().strip()
        try:
            qte = self.qte_var.get()
            if qte <= 0: raise ValueError
        except:
            messagebox.showerror("Erreur", "Quantité invalide.")
            return
            
        # Verify at least one operation is selected
        has_ops = any(step['var_check'].get() for step in self.gamme_vars)
        if not has_ops:
            messagebox.showerror("Erreur", "Veuillez cocher au moins une opération pour créer cet OF.")
            return
            
        cursor = self.db_conn.cursor()
        
        # Générer ID OF unique
        cursor.execute("SELECT ID_OF FROM CdeDetail ORDER BY ID_OF DESC LIMIT 1")
        last_id = cursor.fetchone()
        if last_id and last_id[0].startswith("OF-"):
            try:
                num = int(last_id[0].split("-")[1])
                new_id = f"OF-{num + 1}"
            except:
                new_id = "OF-1000"
        else:
            new_id = "OF-1000"
            
        # Insérer
        try:
            cursor.execute("INSERT INTO CdeDetail (ID_OF, CDE, PROD, DESIGN, OBSERV, Qte, LignesSage) VALUES (?, ?, ?, ?, ?, ?, ?)", (new_id, self.cde, ref_prod, design, obs, qte, self.lignes_sage))
        except sqlite3.OperationalError:
            cursor.execute("INSERT INTO CdeDetail (ID_OF, CDE, PROD, DESIGN, OBSERV, Qte) VALUES (?, ?, ?, ?, ?, ?)", (new_id, self.cde, ref_prod, design, obs, qte))
        
        # Insérer la gamme avec postes assignés, uniquement les étapes cochées
        ordre_counter = 1
        for step in self.gamme_vars:
            if step['var_check'].get():
                val = step['var_poste'].get()
                poste_assigne = val.split(" - ")[0] if val != "Libre (N'importe lequel)" else None
                cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", (new_id, ordre_counter, step['code_op'], poste_assigne))
                ordre_counter += 1
                
        if ordre_counter == 1:
            # Aucune étape cochée, on pourrait bloquer ou accepter. On l'accepte mais on met un log.
            pass
            
        self.db_conn.commit()
        self.result = True
        self.destroy()

class SotraglaceApp:
    def __init__(self, root):
        self.root = root
        
        self.poste_actuel = self.load_config()
        self.poste_nom_court = self.poste_actuel.split("-")[-1].strip()
        
        self.root.title(f"Sotraglace - Tableau de Bord Production - Poste : {self.poste_actuel}")
        self.root.geometry("1280x800")
        def _maximize_safe():
            try:
                self.root.state('zoomed')
            except Exception:
                try:
                    self.root.attributes('-zoomed', True)
                except Exception:
                    pass
        self.root.after(100, _maximize_safe)
        
        # Style global - Thème Industriel Slate Pro (UI/UX Pro Max)
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configuration des Treeview
        self.style.configure("Treeview", 
                             background="#1E293B", foreground="#F8FAFC", 
                             fieldbackground="#1E293B", rowheight=38, font=("Segoe UI", 12),
                             indicatorsize=15, indicatormargins=6)
        self.style.configure("Treeview.Heading", 
                             background="#0F172A", foreground="#94A3B8", 
                             font=("Segoe UI", 11, "bold"), relief="flat")
        self.style.map("Treeview", 
                       background=[('selected', '#2563EB')], 
                       foreground=[('selected', '#FFFFFF')])
        
        # Fond général
        self.style.configure("TFrame", background="#0B1120")
        self.root.configure(fg_color="#0B1120")
        
        self.db_conn = None
        self.init_db()
        
        self.sage_data = {
            "entetes": {}, 
            "lignes": {}   
        }
        
        self.scan_counts = {} # Cache : (QR_Code, Poste) -> count
        
        self.build_ui()
        self.load_sage_data()
        self.refresh_dashboard()
        
        self.scan_entry.focus_set()
        self.root.bind("<Button-1>", lambda e: self.root.after(100, self.scan_entry.focus_set))
        self.root.bind("<Any-KeyPress>", self.force_focus)
        
    def force_focus(self, event):
        # On ne force pas le focus si l'utilisateur tape dans la barre de recherche
        curr_focus = self.root.focus_get()
        search_widgets = (self.search_entry, getattr(self.search_entry, '_entry', None))
        scan_widgets = (self.scan_entry, getattr(self.scan_entry, '_entry', None))
        if curr_focus not in search_widgets and curr_focus not in scan_widgets:
            self.scan_entry.focus_set()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('poste', get_postes_disponibles()[0])
            except Exception:
                pass
                
        dialog = ConfigDialog(self.root)
        self.root.wait_window(dialog)
        poste = dialog.result
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'poste': poste}, f)
        return poste
        
    def init_db(self):
        self.db_conn = sqlite3.connect(DB_FILE)
        cursor = self.db_conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Produits (
                RefProd TEXT PRIMARY KEY,
                DesProd TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Operations (
                RefOp TEXT PRIMARY KEY,
                LibelOp TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Postes (
                CodPost TEXT PRIMARY KEY,
                DesPost TEXT,
                RefOp TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Gammes (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                RefProd TEXT,
                CodeOp TEXT,
                Ordre INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS CdeDetail (
                ID_OF TEXT PRIMARY KEY,
                CDE TEXT,
                PROD TEXT,
                DESIGN TEXT,
                OBSERV TEXT,
                Qte INTEGER DEFAULT 1,
                LignesSage TEXT
            )
        ''')
        
        try:
            cursor.execute("ALTER TABLE CdeDetail ADD COLUMN LignesSage TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS OF_Gammes (
                ID_OF TEXT,
                Ordre INTEGER,
                CodeOp TEXT,
                Poste_Assigne TEXT,
                PRIMARY KEY (ID_OF, Ordre)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Scans (
                ID_Scan INTEGER PRIMARY KEY AUTOINCREMENT,
                ID_OF TEXT NOT NULL,
                Poste TEXT NOT NULL,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                Child_Key TEXT
            )
        ''')
        try:
            cursor.execute("ALTER TABLE Scans ADD COLUMN Child_Key TEXT")
        except sqlite3.OperationalError:
            pass
            
        # Seed default postes et opérations si la table est vide
        cursor.execute("SELECT count(*) FROM Postes")
        if cursor.fetchone()[0] == 0:
            default_ops = [
                ("DEC", "Découpe"),
                ("USI", "Usinage"),
                ("FAC", "Façonnage"),
                ("TRE", "Trempe"),
                ("EXP", "Expédition")
            ]
            cursor.executemany("INSERT OR IGNORE INTO Operations (RefOp, LibelOp) VALUES (?, ?)", default_ops)
            default_postes = [
                ("DEC1", "Découpe Numérique SEKTOR", "DEC"),
                ("USI1", "Centre Usinage 1", "USI"),
                ("FAC1", "Ligne Façonnage 1", "FAC"),
                ("TRE1", "Four Trempe", "TRE"),
                ("EXP1", "Zone Expédition", "EXP")
            ]
            cursor.executemany("INSERT OR IGNORE INTO Postes (CodPost, DesPost, RefOp) VALUES (?, ?, ?)", default_postes)
            
        self.db_conn.commit()

    def detect_encoding(self, filepath):
        encodings = ['utf-8-sig', 'latin-1', 'cp1252']
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    f.readline()
                return enc
            except UnicodeDecodeError:
                continue
    def update_status_bar(self, status_type, message):
        colors = {
            "error": ("#DC2626", "#FFFFFF"),
            "success": ("#059669", "#FFFFFF"),
            "progress": ("#2563EB", "#FFFFFF"),
            "warning": ("#D97706", "#0B1120"),
            "default": ("#1E293B", "#94A3B8")
        }
        bg, fg = colors.get(status_type, ("#1E293B", "#94A3B8"))
        if hasattr(self, 'lbl_scan_status') and self.lbl_scan_status:
            self.lbl_scan_status.configure(text=message, text_color=fg)
        if hasattr(self, 'status_frame') and self.status_frame:
            try:
                self.status_frame.configure(fg_color=bg)
            except Exception:
                pass

    def load_sage_data(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
            self.update_status_bar("error", f"Dossier 'data' créé. Placez-y les CSV Sage.")
            return
            
        file_entetes = os.path.join(DATA_DIR, "F-DOCENTETE.csv")
        if not os.path.exists(file_entetes):
            file_entetes = os.path.join(DATA_DIR, "docentete.csv")
            
        file_lignes = os.path.join(DATA_DIR, "F-DOCLIGNE.csv")
        if not os.path.exists(file_lignes):
            file_lignes = os.path.join(DATA_DIR, "docligne.csv")
        
        entetes = {}
        lignes = {}
        
        if os.path.exists(file_entetes):
            enc = self.detect_encoding(file_entetes)
            with open(file_entetes, 'r', encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=',')
                for row in reader:
                    if 'DO_Piece' in row:
                        do_piece = row['DO_Piece'].strip()
                        if do_piece.startswith('CC'):
                            entetes[do_piece] = row
                        
        if os.path.exists(file_lignes):
            enc = self.detect_encoding(file_lignes)
            with open(file_lignes, 'r', encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=',')
                for row in reader:
                    if 'DO_Piece' in row and 'DL_Ligne' in row:
                        do_piece = row['DO_Piece'].strip()
                        if not do_piece.startswith('CC'):
                            continue
                        dl_ligne = row['DL_Ligne'].strip()
                        key = f"{do_piece}-{dl_ligne}"
                        lignes[key] = row
                        
        self.sage_data['entetes'] = entetes
        self.sage_data['lignes'] = lignes
        
        # Optimisation : grouper les lignes par pièce pour éviter O(N*M)
        lignes_par_piece = {}
        for key, row in lignes.items():
            do_piece = row.get('DO_Piece', '').strip()
            if not do_piece:
                do_piece = key.split('-')[0]
            if do_piece not in lignes_par_piece:
                lignes_par_piece[do_piece] = []
            lignes_par_piece[do_piece].append((key, row))
        self.sage_data['lignes_par_piece'] = lignes_par_piece
        
        # Load all scans counts into memory for fast UI rendering
        self.load_scans_cache()

    
    def get_mon_op(self):
        cursor = self.db_conn.cursor()
        codpost = self.poste_actuel.split(" - ")[0]
        cursor.execute("SELECT RefOp FROM Postes WHERE CodPost = ?", (codpost,))
        row = cursor.fetchone()
        return row[0] if row else None

    def load_scans_cache(self):
        postes_list = get_postes_disponibles()
        self.scans_globaux = {poste: {} for poste in postes_list}
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT Poste, ID_OF, COUNT(*) FROM Scans GROUP BY Poste, ID_OF")
        for row in cursor.fetchall():
            poste, qr, count = row
            if poste in self.scans_globaux:
                self.scans_globaux[poste][qr] = count
                
        self.scan_counts = self.scans_globaux.get(self.poste_actuel, {})


    def get_order_progress(self, do_piece):
        cursor = self.db_conn.cursor()
        mon_op = self.get_mon_op()
        if not mon_op: return 0, 0, "N/A"
        
        # Get all OFs for this order that have 'mon_op' in their routing AND are assigned to me or free
        codpost = self.poste_actuel.split(" - ")[0]
        cursor.execute('''
            SELECT C.ID_OF, C.Qte FROM CdeDetail C
            JOIN OF_Gammes G ON C.ID_OF = G.ID_OF
            WHERE C.CDE = ? AND G.CodeOp = ? AND (G.Poste_Assigne IS NULL OR G.Poste_Assigne = ?)
        ''', (do_piece, mon_op, codpost))
        
        ofs = cursor.fetchall()
        if not ofs:
            return 0, 0, "N/A"
            
        total_qte = sum(of[1] for of in ofs)
        total_scanned = 0
        
        for of_id, qte in ofs:
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
            ''', (of_id, mon_op))
            count = cursor.fetchone()[0]
            total_scanned += min(count, qte)
            
        if total_qte == 0: return 0, 0, "N/A"
        pct = (total_scanned / total_qte) * 100
        return total_scanned, total_qte, f"{pct:.1f}%"

    def build_ui(self):
        # Système d'onglets natif CustomTkinter (Thème Industrial Slate Pro)
        self.notebook = ctk.CTkTabview(
            self.root, 
            command=self.on_main_tab_changed,
            segmented_button_selected_color="#2563EB",
            segmented_button_selected_hover_color="#1D4ED8",
            segmented_button_unselected_color="#1E293B",
            segmented_button_unselected_hover_color="#334155",
            text_color="#F8FAFC",
            text_color_disabled="#64748B"
        )
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=8, pady=6)
        
        # Onglet 1 : Atelier
        self.tab_atelier = self.notebook.add("⚙️ ATELIER (Production)")
        
        # Onglet 2 : Bureau d'Étude
        self.tab_be = self.notebook.add("📐 BUREAU D'ÉTUDE (Nomenclatures)")
        
        # Construction de l'interface Atelier dans tab_atelier
        # 1. Header (Bandeau supérieur moderne avec carte Slate satinée)
        self.header_frame = ctk.CTkFrame(self.tab_atelier, fg_color="#0F172A", height=76, corner_radius=12, border_width=1, border_color="#334155")
        self.header_frame.pack(fill=tk.X, side=tk.TOP, pady=(2, 8))
        self.header_frame.pack_propagate(False)
        
        # Badge Marque & Poste Actuel
        badge_poste = ctk.CTkFrame(self.header_frame, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#2563EB")
        badge_poste.pack(side=tk.LEFT, padx=16, pady=12)
        
        ctk.CTkLabel(badge_poste, text="🏭 SOTRAGLACE MES", font=("Segoe UI", 11, "bold"), text_color="#38BDF8").pack(side=tk.LEFT, padx=(12, 6), pady=8)
        ctk.CTkLabel(badge_poste, text="|", font=("Segoe UI", 12), text_color="#475569").pack(side=tk.LEFT, padx=2)
        self.lbl_title = ctk.CTkLabel(badge_poste, text=f"POSTE : {self.poste_nom_court.upper()}", 
                                      font=("Segoe UI", 15, "bold"), text_color="#F8FAFC")
        self.lbl_title.pack(side=tk.LEFT, padx=(6, 12), pady=8)
        
        # Boutons d'action Header
        btn_poste = ctk.CTkButton(self.header_frame, text="⚙️ Changer de Poste", font=("Segoe UI", 12, "bold"),
                                  fg_color="#D97706", hover_color="#B45309", text_color="white",
                                  height=36, corner_radius=8, command=self.change_poste)
        btn_poste.pack(side=tk.RIGHT, padx=(6, 16), pady=18)
        
        btn_refresh = ctk.CTkButton(self.header_frame, text="🔄 Actualiser CSV", font=("Segoe UI", 12, "bold"),
                                    fg_color="#059669", hover_color="#047857", text_color="white",
                                    height=36, corner_radius=8, command=self.action_refresh)
        btn_refresh.pack(side=tk.RIGHT, padx=6, pady=18)
        
        btn_simu = ctk.CTkButton(self.header_frame, text="🔫 Test Scan", font=("Segoe UI", 12, "bold"),
                                 fg_color="#4F46E5", hover_color="#4338CA", text_color="white",
                                 height=36, corner_radius=8, command=self.open_scan_simulator)
        btn_simu.pack(side=tk.RIGHT, padx=6, pady=18)

        # 3. Footer (Bandeau inférieur de Scan - centre de commande opérateur)
        self.footer_frame = ctk.CTkFrame(self.tab_atelier, fg_color="#0F172A", height=124, corner_radius=12, border_width=1, border_color="#334155")
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 2))
        self.footer_frame.pack_propagate(False)
        
        self.lbl_scan_status = ctk.CTkLabel(self.footer_frame, text="🎯 EN ATTENTE DU SCAN DOUCHETTE", 
                                            font=("Segoe UI", 15, "bold"), text_color="#94A3B8", fg_color="transparent")
        self.lbl_scan_status.pack(pady=(12, 6))
        
        self.scan_var = tk.StringVar()
        self.scan_entry = ctk.CTkEntry(self.footer_frame, textvariable=self.scan_var, font=("Segoe UI", 20, "bold"), 
                                       justify="center", width=520, height=46, corner_radius=10,
                                       border_width=2, border_color="#2563EB", fg_color="#1E293B", text_color="#F8FAFC")
        self.scan_entry.pack(pady=(0, 10))
        self.scan_entry.bind("<Return>", self.on_scan)
        
        self.status_frame = self.footer_frame

        # 2. Body (Zone centrale)
        self.body_frame = ctk.CTkFrame(self.tab_atelier, fg_color="transparent")
        self.body_frame.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)
        
        self.body_frame.columnconfigure(0, weight=6) # Gauche 60%
        self.body_frame.columnconfigure(1, weight=4) # Droite 40%
        self.body_frame.rowconfigure(0, weight=1)
        
        # --- BLOC DROIT (Vue Globale des Commandes) ---
        self.right_col = ctk.CTkFrame(self.body_frame, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)
        
        search_frame = ctk.CTkFrame(self.right_col, fg_color="transparent")
        search_frame.pack(fill=tk.X, padx=12, pady=(12, 8))
        ctk.CTkLabel(search_frame, text="📋 COMMANDES EN ATELIER", font=("Segoe UI", 13, "bold"), text_color="#38BDF8").pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, font=("Segoe UI", 12), width=180, 
                                         corner_radius=8, border_width=1, border_color="#334155", fg_color="#1E293B", text_color="#F8FAFC")
        self.search_entry.pack(side=tk.RIGHT)
        ctk.CTkLabel(search_frame, text="🔍", font=("Segoe UI", 12), text_color="#94A3B8").pack(side=tk.RIGHT, padx=4)

        cols_cmd = ("commande", "date", "client", "avancement")
        tree_cmd_frame = ctk.CTkFrame(self.right_col, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        tree_cmd_frame.pack(expand=True, fill=tk.BOTH, padx=12, pady=(0, 12))
        
        scroll_cmd = ttk.Scrollbar(tree_cmd_frame, orient="vertical")
        
        self.tree_cmd = ttk.Treeview(tree_cmd_frame, columns=cols_cmd, show="headings", selectmode="browse", yscrollcommand=scroll_cmd.set)
        scroll_cmd.config(command=self.tree_cmd.yview)
        
        self.tree_cmd.heading("commande", text="N° Cmd")
        self.tree_cmd.heading("date", text="Date")
        self.tree_cmd.heading("client", text="Client")
        self.tree_cmd.heading("avancement", text="Prog.")
        
        self.tree_cmd.column("commande", width=95)
        self.tree_cmd.column("date", width=85)
        self.tree_cmd.column("client", width=170)
        self.tree_cmd.column("avancement", width=85, anchor="center")
        
        scroll_cmd.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_cmd.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.tree_cmd.tag_configure('terminee', background='#064E3B', foreground='#A7F3D0')
        self.tree_cmd.tag_configure('encours', background='#78350F', foreground='#FDE68A')
        self.tree_cmd.tag_configure('pas_demarre', background='#1E293B', foreground='#94A3B8')
        
        self.tree_cmd.tag_configure('terminee_sel', background='#059669', foreground='#FFFFFF', font=("Segoe UI", 11, "bold"))
        self.tree_cmd.tag_configure('encours_sel', background='#D97706', foreground='#FFFFFF', font=("Segoe UI", 11, "bold"))
        self.tree_cmd.tag_configure('pas_demarre_sel', background='#2563EB', foreground='#FFFFFF', font=("Segoe UI", 11, "bold"))
        self.tree_cmd.tag_configure('default_sel', background='#2563EB', foreground='#FFFFFF', font=("Segoe UI", 11, "bold"))
        self.tree_cmd.bind("<<TreeviewSelect>>", lambda e: [self._update_selection_tags(self.tree_cmd), self.on_order_select(e)])
        
        # --- BLOC GAUCHE (Détails de la commande et Focus Scan) ---
        self.left_col = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        
        # Détails Commande (Haut)
        cmd_info_frame = ctk.CTkFrame(self.left_col, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        cmd_info_frame.pack(fill=tk.X, pady=(0, 8), ipady=4)
        
        self.lbl_commande = ctk.CTkLabel(cmd_info_frame, text="Commande : --", font=("Segoe UI", 16, "bold"), text_color="#38BDF8", anchor="w")
        self.lbl_commande.pack(fill=tk.X, padx=16, pady=(8, 2))
        
        self.lbl_client = ctk.CTkLabel(cmd_info_frame, text="Client : --", font=("Segoe UI", 14), text_color="#F8FAFC", anchor="w")
        self.lbl_client.pack(fill=tk.X, padx=16, pady=(2, 8))
        
        # Tableau Articles (Milieu)
        articles_header = ctk.CTkFrame(self.left_col, fg_color="transparent")
        articles_header.pack(fill=tk.X, pady=(4, 4))
        self.lbl_lignes_title = ctk.CTkLabel(articles_header, text="ARTICLES DE LA COMMANDE", font=("Segoe UI", 13, "bold"), text_color="#94A3B8", anchor="w")
        self.lbl_lignes_title.pack(side=tk.LEFT)
        
        cols_lignes = ("ligne", "ref", "designation", "dim", "qte", "statut", "situation")
        
        tree_lignes_frame = ctk.CTkFrame(self.left_col, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        tree_lignes_frame.pack(fill=tk.X, pady=(0, 8))
        
        scroll_lignes = ttk.Scrollbar(tree_lignes_frame, orient="vertical")
        
        self.tree_lignes = ttk.Treeview(tree_lignes_frame, columns=cols_lignes, show="tree headings", selectmode="browse", height=5, yscrollcommand=scroll_lignes.set)
        scroll_lignes.config(command=self.tree_lignes.yview)
        
        self.tree_lignes.heading("#0", text="")
        self.tree_lignes.column("#0", width=40, stretch=False)
        self.tree_lignes.heading("ligne", text="Type")
        self.tree_lignes.heading("ref", text="Réf")
        self.tree_lignes.heading("designation", text="Désignation")
        self.tree_lignes.heading("dim", text="Dimensions")
        self.tree_lignes.heading("qte", text="Qté")
        self.tree_lignes.heading("statut", text="Statut")
        self.tree_lignes.heading("situation", text="Situation Usine")
        
        self.tree_lignes.column("ligne", width=40)
        self.tree_lignes.column("ref", width=80)
        self.tree_lignes.column("designation", width=190)
        self.tree_lignes.column("dim", width=140)
        self.tree_lignes.column("qte", width=55, anchor="center")
        self.tree_lignes.column("statut", width=95, anchor="center")
        self.tree_lignes.column("situation", width=160)
        
        scroll_lignes.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_lignes.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.tree_lignes.bind("<<TreeviewSelect>>", lambda e: [self._update_selection_tags(self.tree_lignes), self.on_article_select(e)])        
        
        # Barre d'actions manuelles
        self.actions_article_frame = ctk.CTkFrame(self.left_col, fg_color="#0F172A", corner_radius=10, border_width=1, border_color="#334155")
        self.actions_article_frame.pack(fill=tk.X, pady=(0, 8), ipady=4)
        
        ctk.CTkLabel(self.actions_article_frame, text="⚡ Action :", font=("Segoe UI", 11, "bold"), text_color="#94A3B8").pack(side=tk.LEFT, padx=12)
        
        self.btn_scan_one = ctk.CTkButton(self.actions_article_frame, text="+1 Scanner", fg_color="#2563EB", hover_color="#1D4ED8", text_color="white", font=("Segoe UI", 11, "bold"), height=32, corner_radius=6, command=lambda: self.manual_scan(1))
        self.btn_scan_one.pack(side=tk.LEFT, padx=4)
        
        self.btn_scan_all = ctk.CTkButton(self.actions_article_frame, text="++ TOUT Scanner", fg_color="#059669", hover_color="#047857", text_color="white", font=("Segoe UI", 11, "bold"), height=32, corner_radius=6, command=lambda: self.manual_scan("all"))
        self.btn_scan_all.pack(side=tk.LEFT, padx=4)
        
        self.btn_unscan_one = ctk.CTkButton(self.actions_article_frame, text="-1 Descanner", fg_color="#D97706", hover_color="#B45309", text_color="white", font=("Segoe UI", 11, "bold"), height=32, corner_radius=6, command=lambda: self.manual_unscan(1))
        self.btn_unscan_one.pack(side=tk.LEFT, padx=4)
        
        self.btn_unscan_all = ctk.CTkButton(self.actions_article_frame, text="-- TOUT Annuler", fg_color="#DC2626", hover_color="#B91C1C", text_color="white", font=("Segoe UI", 11, "bold"), height=32, corner_radius=6, command=lambda: self.manual_unscan("all"))
        self.btn_unscan_all.pack(side=tk.LEFT, padx=4)
        
        self.tree_lignes.tag_configure('terminee', background='#064E3B', foreground='#A7F3D0')
        self.tree_lignes.tag_configure('encours', background='#78350F', foreground='#FDE68A')
        self.tree_lignes.tag_configure('pret', background='#1E3A8A', foreground='#BFDBFE')
        self.tree_lignes.tag_configure('attente', background='#1E293B', foreground='#94A3B8')
        self.tree_lignes.tag_configure('pas_demarre', background='#1E293B', foreground='#94A3B8')
        self.tree_lignes.tag_configure('erreur', background='#7F1D1D', foreground='#FECACA')
        self.tree_lignes.tag_configure('child', foreground='#94A3B8')
        
        font_sel = ("Segoe UI", 11, "bold")
        sel_blue = '#2563EB'
        self.tree_lignes.tag_configure('terminee_sel', background='#059669', foreground='white', font=font_sel) 
        self.tree_lignes.tag_configure('encours_sel', background='#D97706', foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('pret_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('attente_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('pas_demarre_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('erreur_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('child_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('default_sel', background=sel_blue, foreground='white', font=font_sel)

        # Focus Industriel / Radar (Bas gauche)
        self.bottom_left_container = ctk.CTkFrame(self.left_col, fg_color="transparent")
        self.bottom_left_container.pack(expand=True, fill=tk.BOTH)
        
        # --- FRAME 1 : Le Radar / Frise globale ---
        self.timeline_frame = ctk.CTkFrame(self.bottom_left_container, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        self.timeline_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.lbl_article_details = ctk.CTkLabel(self.timeline_frame, text="Sélectionnez un article pour afficher son parcours de production", 
                                               font=("Segoe UI", 13, "bold"), text_color="#38BDF8", wraplength=500, justify="center")
        self.lbl_article_details.pack(pady=(10, 4))
        
        self.frise_frame = ctk.CTkFrame(self.timeline_frame, fg_color="transparent")
        self.frise_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))
        
        self.timeline_blocks = {}
        postes_list = get_postes_disponibles()
        for i, poste in enumerate(postes_list):
            poste_nom = poste.split("-")[-1].strip()
            is_current = (poste == self.poste_actuel)
            border_c = "#2563EB" if is_current else "#334155"
            border_w = 2 if is_current else 1
            card_c = "#162032" if is_current else "#1E293B"
            
            block = ctk.CTkFrame(self.frise_frame, fg_color=card_c, corner_radius=10, border_width=border_w, border_color=border_c)
            self.frise_frame.columnconfigure(i, weight=1)
            block.grid(row=0, column=i, sticky="nsew", padx=3, pady=6)
            
            title_color = "#38BDF8" if is_current else "#94A3B8"
            lbl_nom = ctk.CTkLabel(block, text=poste_nom, font=("Segoe UI", 11, "bold"), text_color=title_color, wraplength=95)
            lbl_nom.pack(pady=(8, 0))
            
            lbl_count = ctk.CTkLabel(block, text="0 / 0", font=("Segoe UI", 22, "bold"), text_color="#F8FAFC")
            lbl_count.pack(expand=True, pady=4)
            
            self.timeline_blocks[poste] = {'frame': block, 'lbl_nom': lbl_nom, 'lbl_count': lbl_count}
            
        # --- FRAME 2 : Focus Flash Scan (Pendant le scan) ---
        self.scan_flash_frame = ctk.CTkFrame(self.bottom_left_container, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        
        self.scan_flash_frame.columnconfigure(0, weight=1)
        self.scan_flash_frame.columnconfigure(1, weight=1)
        self.scan_flash_frame.rowconfigure(0, weight=1)
        
        dim_info = ctk.CTkFrame(self.scan_flash_frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        dim_info.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.lbl_designation = ctk.CTkLabel(dim_info, text="Désignation : --", font=("Segoe UI", 14, "bold"), text_color="#F8FAFC", wraplength=280, justify="left")
        self.lbl_designation.pack(pady=(12, 6), padx=10)
        
        self.dim_frame = ctk.CTkFrame(dim_info, fg_color="#162032", corner_radius=8, border_width=1, border_color="#2563EB")
        self.dim_frame.pack(fill=tk.X, padx=12, pady=8)
        self.lbl_dim = ctk.CTkLabel(self.dim_frame, text="DIMENSIONS\n-- x --", font=("Segoe UI", 24, "bold"), text_color="#38BDF8")
        self.lbl_dim.pack(pady=12)

        prog_info = ctk.CTkFrame(self.scan_flash_frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        prog_info.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.lbl_progression_title = ctk.CTkLabel(prog_info, text="PROGRESSION DE L'OF", font=("Segoe UI", 12, "bold"), text_color="#94A3B8")
        self.lbl_progression_title.pack(pady=(12, 0))
        
        self.lbl_progression = ctk.CTkLabel(prog_info, text="0 / 0", font=("Segoe UI", 80, "bold"), text_color="#F8FAFC")
        self.lbl_progression.pack(expand=True, pady=(0, 8))
        
        # Construction de l'interface Bureau d'Étude
        self.build_be_ui()
        
    def build_be_ui(self):
        # Header BE
        header_be = ctk.CTkFrame(self.tab_be, fg_color="#0F172A", height=74, corner_radius=12, border_width=1, border_color="#334155")
        header_be.pack(fill=tk.X, side=tk.TOP, pady=(2, 8))
        header_be.pack_propagate(False)
        
        badge_be = ctk.CTkFrame(header_be, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#2563EB")
        badge_be.pack(side=tk.LEFT, padx=16, pady=12)
        
        self.lbl_be_header = ctk.CTkLabel(badge_be, text="📐 BUREAU D'ÉTUDE", font=("Segoe UI", 15, "bold"), text_color="#F8FAFC")
        self.lbl_be_header.pack(side=tk.LEFT, padx=14, pady=8)
        
        # Notebook BE natif CustomTkinter
        self.be_notebook = ctk.CTkTabview(
            self.tab_be, 
            command=self.on_be_tab_changed,
            segmented_button_selected_color="#2563EB",
            segmented_button_selected_hover_color="#1D4ED8",
            segmented_button_unselected_color="#1E293B",
            segmented_button_unselected_hover_color="#334155",
            text_color="#F8FAFC"
        )
        self.be_notebook.pack(expand=True, fill=tk.BOTH, padx=4, pady=4)
        
        self.tab_be_gen = self.be_notebook.add("📝 Génération OF")
        self.tab_be_matrice = self.be_notebook.add("📊 Matrice Commandes")
        self.tab_be_charge = self.be_notebook.add("🏭 Charge Machines")
        
        self.build_be_gen_ui()
        self.build_be_matrice_ui()
        self.build_be_charge_ui()

    def on_main_tab_changed(self, event=None):
        tab_text = self.notebook.get() if hasattr(self.notebook, "get") else ""
        if "BUREAU" in tab_text:
            if hasattr(self, "be_notebook"):
                be_tab_text = self.be_notebook.get() if hasattr(self.be_notebook, "get") else ""
                if "Matrice" in be_tab_text:
                    self.refresh_be_matrice()
                elif "Charge" in be_tab_text:
                    self.refresh_be_charge()

    def on_be_tab_changed(self, event=None):
        tab_text = self.be_notebook.get() if hasattr(self.be_notebook, "get") else ""
        if "Matrice" in tab_text:
            self.refresh_be_matrice()
        elif "Charge" in tab_text:
            self.refresh_be_charge()
        self.lbl_be_header.configure(text=f"📐 BUREAU D'ÉTUDE - {tab_text}")
        
        if "Matrice" in tab_text:
            self.refresh_be_matrice()
        elif "Charge" in tab_text:
            self.refresh_be_charge()

    def build_be_gen_ui(self):
        # Body BE Gen
        body_be = ctk.CTkFrame(self.tab_be_gen, fg_color="transparent")
        body_be.pack(expand=True, fill=tk.BOTH, padx=4, pady=4)
        
        body_be.columnconfigure(0, weight=3) # Commandes (30%)
        body_be.columnconfigure(1, weight=7) # Détails (70%)
        body_be.rowconfigure(0, weight=1)
        
        # --- Gauche : Commandes ---
        left_be = ctk.CTkFrame(body_be, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        left_be.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(left_be, text="📋 COMMANDES SAGE", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(pady=(12, 6))
        
        cols_be_cmd = ("cmd", "client")
        tree_be_cmd_frame = ctk.CTkFrame(left_be, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        tree_be_cmd_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))
        
        scroll_be_cmd = ttk.Scrollbar(tree_be_cmd_frame, orient="vertical")
        
        self.tree_be_cmd = ttk.Treeview(tree_be_cmd_frame, columns=cols_be_cmd, show="headings", selectmode="browse", yscrollcommand=scroll_be_cmd.set)
        scroll_be_cmd.config(command=self.tree_be_cmd.yview)
        
        self.tree_be_cmd.heading("cmd", text="Commande")
        self.tree_be_cmd.heading("client", text="Client")
        self.tree_be_cmd.column("cmd", width=100)
        self.tree_be_cmd.column("client", width=150)
        
        scroll_be_cmd.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_be_cmd.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.tree_be_cmd.tag_configure('terminee', background='#064E3B', foreground='#A7F3D0')
        self.tree_be_cmd.tag_configure('encours', background='#78350F', foreground='#FDE68A')
        self.tree_be_cmd.tag_configure('pas_demarre', background='#1E293B', foreground='#94A3B8')
        
        self.tree_be_cmd.tag_configure('terminee_sel', background='#059669', foreground='white', font=("Segoe UI", 10, "bold"))
        self.tree_be_cmd.tag_configure('encours_sel', background='#D97706', foreground='white', font=("Segoe UI", 10, "bold"))
        self.tree_be_cmd.tag_configure('pas_demarre_sel', background='#2563EB', foreground='white', font=("Segoe UI", 10, "bold"))
        self.tree_be_cmd.tag_configure('default_sel', background='#2563EB', foreground='white', font=("Segoe UI", 10, "bold"))
        self.tree_be_cmd.bind("<<TreeviewSelect>>", lambda e: [self._update_selection_tags(self.tree_be_cmd), self.on_be_order_select(e)])
        
        font_sel = ("Segoe UI", 10, "bold")
        sel_blue = '#2563EB'
        
        # --- Droite : Détails ---
        right_be = ctk.CTkFrame(body_be, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        right_be.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        
        # Haut: Lignes Sage
        ctk.CTkLabel(right_be, text="📦 LIGNES COMMERCIALES (SAGE)", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(pady=(12, 4))
        
        cols_be_sage = ("ligne", "ref", "designation", "dim", "qte")
        tree_be_sage_frame = ctk.CTkFrame(right_be, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        tree_be_sage_frame.pack(fill=tk.X, padx=10, pady=4)
        
        scroll_be_sage = ttk.Scrollbar(tree_be_sage_frame, orient="vertical")
        
        self.tree_be_sage = ttk.Treeview(tree_be_sage_frame, columns=cols_be_sage, show="headings", height=5, yscrollcommand=scroll_be_sage.set, selectmode="browse")
        scroll_be_sage.config(command=self.tree_be_sage.yview)
        
        self.tree_be_sage.heading("ligne", text="Ligne")
        self.tree_be_sage.heading("ref", text="Réf Sage")
        self.tree_be_sage.heading("designation", text="Désignation Sage")
        self.tree_be_sage.heading("dim", text="Dimensions")
        self.tree_be_sage.heading("qte", text="Qté")
        self.tree_be_sage.column("ligne", width=50)
        self.tree_be_sage.column("ref", width=100)
        self.tree_be_sage.column("designation", width=250)
        self.tree_be_sage.column("dim", width=100)
        self.tree_be_sage.column("qte", width=50, anchor="center")
        
        scroll_be_sage.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_be_sage.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.tree_be_sage.bind("<<TreeviewSelect>>", lambda e: self._update_selection_tags(self.tree_be_sage))
        self.tree_be_sage.tag_configure('default_sel', background=sel_blue, foreground='white', font=font_sel)
        
        # Bas: Sous-ensembles (OF)
        ctk.CTkLabel(right_be, text="🏭 SOUS-ENSEMBLES DE FABRICATION (Nomenclature Atelier)", font=("Segoe UI", 12, "bold"), text_color="#34D399").pack(pady=(12, 4))
        
        # Actions BE
        action_frame = ctk.CTkFrame(right_be, fg_color="transparent")
        action_frame.pack(fill=tk.X, padx=10, pady=4)
        btn_add_of = ctk.CTkButton(action_frame, text="➕ Créer l'OF", fg_color="#059669", hover_color="#047857", text_color="white", font=("Segoe UI", 11, "bold"), height=32, corner_radius=6, command=self.add_of_dialog)
        btn_add_of.pack(side=tk.LEFT, padx=4)
        btn_print = ctk.CTkButton(action_frame, text="🖨️ Imprimer Étiquettes", fg_color="#2563EB", hover_color="#1D4ED8", text_color="white", font=("Segoe UI", 11, "bold"), height=32, corner_radius=6)
        btn_print.pack(side=tk.LEFT, padx=4)
        
        cols_be_of = ("id", "prod", "design", "observ", "qte", "parcours")
        tree_be_of_frame = ctk.CTkFrame(right_be, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        tree_be_of_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=(4, 10))
        
        scroll_be_of = ttk.Scrollbar(tree_be_of_frame, orient="vertical")
        
        self.tree_be_of = ttk.Treeview(tree_be_of_frame, columns=cols_be_of, show="tree headings", height=10, yscrollcommand=scroll_be_of.set)
        scroll_be_of.config(command=self.tree_be_of.yview)
        
        self.tree_be_of.heading("#0", text="")
        self.tree_be_of.column("#0", width=40, stretch=False)
        self.tree_be_of.heading("id", text="N° OF")
        self.tree_be_of.heading("prod", text="Réf Produit")
        self.tree_be_of.heading("design", text="Désignation Atelier")
        self.tree_be_of.heading("observ", text="Observations / Détails")
        self.tree_be_of.heading("qte", text="Qté")
        self.tree_be_of.heading("parcours", text="Gammes / Postes assignés")
        
        self.tree_be_of.column("id", width=80, anchor="center")
        self.tree_be_of.column("prod", width=100)
        self.tree_be_of.column("design", width=200)
        self.tree_be_of.column("observ", width=150)
        self.tree_be_of.column("qte", width=50, anchor="center")
        self.tree_be_of.column("parcours", width=250)
        
        scroll_be_of.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_be_of.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.tree_be_of.bind("<<TreeviewSelect>>", lambda e: self._update_selection_tags(self.tree_be_of))
        self.tree_be_of.tag_configure('default_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_be_of.tag_configure('child_sel', background=sel_blue, foreground='white', font=font_sel)

    def change_poste(self):
        dialog = ConfigDialog(self.root, is_cancellable=True)
        self.root.wait_window(dialog)
        
        if dialog.result and dialog.result != self.poste_actuel:
            self.poste_actuel = dialog.result
            self.poste_nom_court = self.poste_actuel.split("-")[-1].strip()
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'poste': self.poste_actuel}, f)
                
            self.lbl_title.configure(text=f"TABLEAU DE BORD | POSTE : {self.poste_nom_court.upper()}")
            self.root.title(f"Sotraglace - Tableau de Bord Production - Poste : {self.poste_actuel}")
            
            self.load_scans_cache()
            self.refresh_dashboard(filter_text=self.search_var.get().lower())
            
            selected = self.tree_cmd.selection()
            if selected:
                self.update_lines_view(selected[0])
            else:
                for item in self.tree_lignes.get_children():
                    self.tree_lignes.delete(item)
                    
        self.scan_entry.focus_set()

    def action_refresh(self):
        self.load_sage_data()
        self.refresh_dashboard()
        self.update_status_bar("default", "DONNÉES SAGE ACTUALISÉES")
        self.scan_entry.focus_set()
        
    def on_search_change(self, *args):
        self.refresh_dashboard(filter_text=self.search_var.get().lower())

    def refresh_dashboard(self, filter_text=""):
        # Vider l'arbre
        for item in self.tree_cmd.get_children():
            self.tree_cmd.delete(item)
            
        orders = []
        for do_piece, entete in self.sage_data['entetes'].items():
            client = entete.get("DO_Tiers", "")
            if filter_text and (filter_text not in do_piece.lower() and filter_text not in client.lower()):
                continue
                
            scanned, total, pct_str = self.get_order_progress(do_piece)
            
            # Si total == 0, ça veut dire qu'il n'y a AUCUN OF pour cette commande 
            # qui passe par le poste de travail actuel. On ne l'affiche pas !
            if total == 0:
                continue
            
            # Déterminer le tag de couleur
            tag = "pas_demarre"
            if total > 0:
                if scanned >= total:
                    tag = "terminee"
                elif scanned > 0:
                    tag = "encours"
                    
            orders.append({
                "values": (do_piece, entete.get("DO_Date", ""), client, f"{scanned}/{total} ({pct_str})"),
                "tag": tag,
                "scanned": scanned,
                "total": total
            })
            
        # Tri (les "En cours" en premier, puis "A faire", puis "Terminée")
        def sort_key(o):
            if o['tag'] == 'encours': return 0
            if o['tag'] == '': return 1
            return 2
            
        orders.sort(key=sort_key)
        
        for o in orders:
            self.tree_cmd.insert("", "end", iid=o['values'][0], values=o['values'], tags=(o['tag'],))
            
        # Rafraîchir aussi la liste des commandes BE
        for item in self.tree_be_cmd.get_children():
            self.tree_be_cmd.delete(item)
            
        be_orders = []
        for do_piece, entete in self.sage_data['entetes'].items():
            client = entete.get("DO_Tiers", "")
            if filter_text and (filter_text not in do_piece.lower() and filter_text not in client.lower()):
                continue
                
            # Pour le BE, on veut toutes les commandes, même si total == 0
            scanned, total, pct_str = self.get_order_progress(do_piece)
            
            tag = "pas_demarre"
            if total > 0:
                if scanned >= total:
                    tag = "terminee"
                elif scanned > 0:
                    tag = "encours"
            else:
                tag = "pas_demarre"
                
            be_orders.append({
                "values": (do_piece, client),
                "tag": tag
            })
            
        # Tri (En cours, puis pas démarré, puis terminé)
        def sort_be(o):
            if o['tag'] == 'encours': return 0
            if o['tag'] == 'pas_demarre': return 1
            return 2
            
        be_orders.sort(key=sort_be)
        
        for o in be_orders:
            self.tree_be_cmd.insert("", "end", iid=o['values'][0], values=o['values'], tags=(o['tag'],))

    def on_be_order_select(self, event):
        self._update_selection_tags(self.tree_be_cmd)
        
        selected = self.tree_be_cmd.selection()
        if not selected: return
        do_piece = selected[0]
        
        # 1. Charger les lignes Sage de cette commande
        for item in self.tree_be_sage.get_children():
            self.tree_be_sage.delete(item)
            
        lignes_cmd = self.sage_data.get('lignes_par_piece', {}).get(do_piece, [])
        lignes_cmd.sort(key=lambda x: x[1].get('DL_Ligne', ''))
        
        for key, ligne in lignes_cmd:
            dl_ligne = ligne.get("DL_Ligne", "")
            ref = ligne.get("AR_Ref", "")
            designation = ligne.get("DL_Design", "")
            longueur = ligne.get("LONG", "")
            largeur = ligne.get("LARG", "")
            dim = f"{longueur}x{largeur}" if longueur and largeur else ""
            try:
                qte = int(float(str(ligne.get("DL_Qte", "1")).replace(',', '.')))
            except ValueError:
                qte = 1
            
            self.tree_be_sage.insert("", "end", iid=key, values=(dl_ligne, ref, designation, dim, qte))
            
        # 2. Charger les OF (Sous-ensembles) existants pour cette commande
        for item in self.tree_be_of.get_children():
            self.tree_be_of.delete(item)
            
        # Create a dict for quick line lookup
        lignes_dict = {key: ligne for key, ligne in lignes_cmd}
        
        cursor = self.db_conn.cursor()
        try:
            cursor.execute("SELECT ID_OF, PROD, DESIGN, OBSERV, Qte, LignesSage FROM CdeDetail WHERE CDE = ?", (do_piece,))
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor.execute("SELECT ID_OF, PROD, DESIGN, OBSERV, Qte FROM CdeDetail WHERE CDE = ?", (do_piece,))
            rows = [list(r) + [""] for r in cursor.fetchall()]
            
        for row in rows:
            id_of, prod, design, obs, qte, lignes_sage = row
            
            # Fetch the selected routing (gammes/postes)
            cursor.execute("SELECT CodeOp, Poste_Assigne FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (id_of,))
            gammes_list = cursor.fetchall()
            parcours_str = ", ".join([f"{op}" + (f" [{poste}]" if poste else "") for op, poste in gammes_list])
            
            self.tree_be_of.insert("", "end", iid=id_of, values=(id_of, prod, design, obs, qte, parcours_str), open=False)
            
            if lignes_sage:
                lignes_keys = lignes_sage.split(",")
                for l_key in lignes_keys:
                    l_key = l_key.strip()
                    ligne_data = lignes_dict.get(l_key) or lignes_dict.get(f"{do_piece}-{l_key}")
                    if ligne_data:
                        dl_ligne = ligne_data.get("DL_Ligne", "")
                        ref = ligne_data.get("AR_Ref", "")
                        des_sage = ligne_data.get("DL_Design", "")
                        longueur = ligne_data.get("LONG", "")
                        largeur = ligne_data.get("LARG", "")
                        dim = f"{longueur}x{largeur}" if longueur and largeur else ""
                        try:
                            l_qte = int(float(str(ligne_data.get("DL_Qte", "1")).replace(',', '.')))
                        except:
                            l_qte = 1
                            
                        # Insert as child
                        child_iid = f"{id_of}_{l_key}"
                        self.tree_be_of.insert(id_of, "end", iid=child_iid, values=(f"↳ Ligne {dl_ligne}", ref, des_sage, f"Dim: {dim}", l_qte, ""), tags=('child',))
                        
        self.tree_be_of.tag_configure('child', foreground='#888888')

    def add_of_dialog(self):
        selected = self.tree_be_cmd.selection()
        if not selected:
            messagebox.showwarning("Attention", "Veuillez d'abord sélectionner une commande.")
            return
            
        do_piece = selected[0]
        
        default_qte = 1
        default_design = ""
        default_obs = ""
        
        # Check if Sage lines are selected to pre-fill
        selected_sage = self.tree_be_sage.selection()
        lignes_sage_list = []
        
        if selected_sage:
            # We take the designation of the FIRST selected item
            item_first = self.tree_be_sage.item(selected_sage[0])
            vals_first = item_first.get('values', [])
            if len(vals_first) >= 5:
                default_design = str(vals_first[2])
                # default_obs remains empty as requested
            
            # We sum the quantity of ALL selected items and record their IDs
            default_qte = 0
            for s in selected_sage:
                item = self.tree_be_sage.item(s)
                vals = item.get('values', [])
                lignes_sage_list.append(str(s)) # the iid of tree_be_sage is the key (or ligne number)
                if len(vals) >= 5:
                    try:
                        default_qte += int(float(vals[4]))
                    except:
                        pass
                        
            if default_qte == 0:
                default_qte = 1
                
        lignes_sage_str = ",".join(lignes_sage_list)
                    
        dialog = AddOfDialog(self.root, self.db_conn, do_piece, default_qte, default_design, default_obs, lignes_sage_str)
        self.root.wait_window(dialog)
        
        if dialog.result:
            # Refresh OFs list
            self.on_be_order_select(None)
            self.update_status_bar("success", "Ordre de Fabrication créé avec succès !")

    def build_be_matrice_ui(self):
        header_mat = ctk.CTkFrame(self.tab_be_matrice, fg_color="#0F172A", height=68, corner_radius=12, border_width=1, border_color="#334155")
        header_mat.pack(fill=tk.X, side=tk.TOP, pady=(2, 8))
        header_mat.pack_propagate(False)
        
        badge_mat = ctk.CTkFrame(header_mat, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#2563EB")
        badge_mat.pack(side=tk.LEFT, padx=16, pady=12)
        ctk.CTkLabel(badge_mat, text="📊 MATRICE D'AVANCEMENT DES COMMANDES", font=("Segoe UI", 14, "bold"), text_color="#38BDF8").pack(padx=14, pady=6)
        
        btn_refresh = ctk.CTkButton(header_mat, text="🔄 Actualiser Matrice", font=("Segoe UI", 12, "bold"), 
                                    fg_color="#059669", hover_color="#047857", text_color="white", 
                                    height=36, corner_radius=8, command=self.refresh_be_matrice)
        btn_refresh.pack(side=tk.RIGHT, padx=16, pady=16)
        
        body_mat = ctk.CTkFrame(self.tab_be_matrice, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        body_mat.pack(expand=True, fill=tk.BOTH, padx=4, pady=4)
        
        scroll_y = ttk.Scrollbar(body_mat, orient="vertical")
        scroll_x = ttk.Scrollbar(body_mat, orient="horizontal")
        
        self.tree_matrice = ttk.Treeview(body_mat, xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set, show="tree headings")
        scroll_y.config(command=self.tree_matrice.yview)
        scroll_x.config(command=self.tree_matrice.xview)
        
        self.tree_matrice.heading("#0", text="Désignation (Hiérarchie)")
        self.tree_matrice.column("#0", width=420, anchor="w")
        
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree_matrice.pack(expand=True, fill=tk.BOTH)
        
        # Tags for 3 states - Modern Industrial Slate Colors
        self.tree_matrice.tag_configure("pas_demarre", background="#1E293B", foreground="#94A3B8")
        self.tree_matrice.tag_configure("encours", background="#78350F", foreground="#FDE68A")
        self.tree_matrice.tag_configure("terminee", background="#064E3B", foreground="#A7F3D0")
        
        font_sel = ("Segoe UI", 11, "bold")
        self.tree_matrice.tag_configure("pas_demarre_sel", background="#2563EB", foreground="#FFFFFF", font=font_sel)
        self.tree_matrice.tag_configure("encours_sel", background="#D97706", foreground="#FFFFFF", font=font_sel)
        self.tree_matrice.tag_configure("terminee_sel", background="#059669", foreground="#FFFFFF", font=font_sel)
        self.tree_matrice.tag_configure("default_sel", background="#2563EB", foreground="#FFFFFF", font=font_sel)
        
        self.tree_matrice.bind("<<TreeviewSelect>>", lambda e: self._update_selection_tags(self.tree_matrice))

    def refresh_be_matrice(self):
        for item in self.tree_matrice.get_children():
            self.tree_matrice.delete(item)
            
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT RefOp, LibelOp FROM Operations ORDER BY RefOp")
        operations = cursor.fetchall()
        
        columns = [op[1] for op in operations]
        self.tree_matrice["columns"] = columns
        for op in operations:
            self.tree_matrice.heading(op[1], text=op[1])
            self.tree_matrice.column(op[1], width=120, anchor="center")
            
        cursor.execute("SELECT DISTINCT CDE FROM CdeDetail")
        commandes = [r[0] for r in cursor.fetchall()]
        
        for cde in commandes:
            cursor.execute("SELECT ID_OF, PROD, DESIGN, LignesSage FROM CdeDetail WHERE CDE = ?", (cde,))
            ofs = cursor.fetchall()
            
            cde_node = self.tree_matrice.insert("", "end", text=f"📦 CDE {cde}", open=False)
            
            cde_total_scans_any = 0
            cde_all_done = True
            cde_has_ops = False
            
            for of in ofs:
                id_of, prod, design, lignes_sage = of
                of_node = self.tree_matrice.insert(cde_node, "end", text=f"⚙️ {id_of} - {design}", open=False)
                
                # Fetch OF Gammes
                cursor.execute("SELECT CodeOp FROM OF_Gammes WHERE ID_OF = ?", (id_of,))
                of_ops = [r[0] for r in cursor.fetchall()]
                
                if not of_ops:
                    continue
                    
                cde_has_ops = True
                
                # We need to construct children if LignesSage has multiple
                child_lines = []
                if lignes_sage:
                    for l in lignes_sage.split(","):
                        l = l.strip()
                        if l: child_lines.append(l)
                
                of_total_scans_any = 0
                of_all_done = True
                
                of_op_texts = []
                for op in operations:
                    ref_op = op[0]
                    if ref_op not in of_ops:
                        of_op_texts.append("-")
                        continue
                        
                    # Calculate total scans for this operation on this OF
                    cursor.execute('''
                        SELECT COUNT(*) FROM Scans 
                        JOIN Postes ON Scans.Poste = Postes.CodPost 
                        WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
                    ''', (id_of, ref_op))
                    mon_scans = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT Qte FROM CdeDetail WHERE ID_OF = ?", (id_of,))
                    qte_totale = cursor.fetchone()[0]
                    
                    of_total_scans_any += mon_scans
                    if mon_scans < qte_totale:
                        of_all_done = False
                        
                    of_op_texts.append(f"{mon_scans}/{qte_totale}")
                    
                self.tree_matrice.item(of_node, values=of_op_texts)
                
                if of_total_scans_any == 0:
                    self.tree_matrice.item(of_node, tags=("pas_demarre",))
                elif of_all_done:
                    self.tree_matrice.item(of_node, tags=("terminee",))
                else:
                    self.tree_matrice.item(of_node, tags=("encours",))
                    
                cde_total_scans_any += of_total_scans_any
                if not of_all_done:
                    cde_all_done = False
                    
                # Children
                if child_lines:
                    lignes_dict = {k: v for k, v in self.sage_data.get('lignes_par_piece', {}).get(cde, [])}
                    for c_key in child_lines:
                        c_data = lignes_dict.get(c_key, {})
                        c_design = c_data.get("DL_Design", "Ligne")
                        try:
                            c_qte = int(float(str(c_data.get("DL_Qte", "1")).replace(',', '.')))
                        except:
                            c_qte = 1
                            
                        c_node = self.tree_matrice.insert(of_node, "end", text=f"↳ Ligne {c_key} - {c_design}", open=False)
                        c_op_texts = []
                        
                        c_total_scans = 0
                        c_all_done = True
                        for op in operations:
                            ref_op = op[0]
                            if ref_op not in of_ops:
                                c_op_texts.append("-")
                                continue
                            
                            cursor.execute('''
                                SELECT COUNT(*) FROM Scans 
                                JOIN Postes ON Scans.Poste = Postes.CodPost 
                                WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key = ?
                            ''', (id_of, ref_op, c_key))
                            c_scans = cursor.fetchone()[0]
                            c_total_scans += c_scans
                            if c_scans < c_qte:
                                c_all_done = False
                            c_op_texts.append(f"{c_scans}/{c_qte}")
                            
                        self.tree_matrice.item(c_node, values=c_op_texts)
                        if c_total_scans == 0:
                            self.tree_matrice.item(c_node, tags=("pas_demarre",))
                        elif c_all_done:
                            self.tree_matrice.item(c_node, tags=("terminee",))
                        else:
                            self.tree_matrice.item(c_node, tags=("encours",))
            
            if not cde_has_ops:
                self.tree_matrice.item(cde_node, tags=("pas_demarre",))
            else:
                if cde_total_scans_any == 0:
                    self.tree_matrice.item(cde_node, tags=("pas_demarre",))
                elif cde_all_done:
                    self.tree_matrice.item(cde_node, tags=("terminee",))
                else:
                    self.tree_matrice.item(cde_node, tags=("encours",))


    def build_be_charge_ui(self):
        header_charge = ctk.CTkFrame(self.tab_be_charge, fg_color="#0F172A", height=68, corner_radius=12, border_width=1, border_color="#334155")
        header_charge.pack(fill=tk.X, side=tk.TOP, pady=(2, 8))
        header_charge.pack_propagate(False)
        
        badge_charge = ctk.CTkFrame(header_charge, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#2563EB")
        badge_charge.pack(side=tk.LEFT, padx=16, pady=12)
        ctk.CTkLabel(badge_charge, text="🏭 CHARGE DES POSTES & MACHINES", font=("Segoe UI", 14, "bold"), text_color="#38BDF8").pack(padx=14, pady=6)
        
        btn_refresh = ctk.CTkButton(header_charge, text="🔄 Actualiser Charge", font=("Segoe UI", 12, "bold"), 
                                    fg_color="#059669", hover_color="#047857", text_color="white", 
                                    height=36, corner_radius=8, command=self.refresh_be_charge)
        btn_refresh.pack(side=tk.RIGHT, padx=16, pady=16)
        
        body = ctk.CTkFrame(self.tab_be_charge, fg_color="transparent")
        body.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)
        
        # Colonne gauche (Sélection Machine)
        left_frame = ctk.CTkFrame(body, fg_color="#0F172A", width=320, corner_radius=12, border_width=1, border_color="#334155")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left_frame.pack_propagate(False)
        
        ctk.CTkLabel(left_frame, text="⚙️ SÉLECTION DU POSTE / MACHINE", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(pady=(12, 6))
        
        tree_mach_frame = ctk.CTkFrame(left_frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        tree_mach_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))
        
        scroll_mach = ttk.Scrollbar(tree_mach_frame, orient="vertical")
        self.tree_machines = ttk.Treeview(tree_mach_frame, columns=("machine",), show="headings", yscrollcommand=scroll_mach.set)
        scroll_mach.config(command=self.tree_machines.yview)
        
        self.tree_machines.heading("machine", text="Poste / Machine")
        scroll_mach.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_machines.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.tree_machines.bind("<<TreeviewSelect>>", self.on_machine_select)
        
        self.tree_machines.tag_configure('default_sel', background='#2563EB', foreground='#FFFFFF', font=("Segoe UI", 11, "bold"))
        
        # Colonne droite (Colonnes Kanban)
        right_frame = ctk.CTkFrame(body, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        right_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(6, 0))
        
        right_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(1, weight=1)
        right_frame.columnconfigure(2, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        # En-têtes des 3 colonnes Kanban
        h_attente = ctk.CTkFrame(right_frame, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#334155")
        h_attente.grid(row=0, column=0, sticky="ew", padx=8, pady=(10, 6), ipady=4)
        ctk.CTkLabel(h_attente, text="📥 À FAIRE / EN ATTENTE", font=("Segoe UI", 12, "bold"), text_color="#94A3B8").pack(pady=4)
        
        h_encours = ctk.CTkFrame(right_frame, fg_color="#78350F", corner_radius=8, border_width=1, border_color="#D97706")
        h_encours.grid(row=0, column=1, sticky="ew", padx=8, pady=(10, 6), ipady=4)
        ctk.CTkLabel(h_encours, text="⏳ EN COURS DE FABRICATION", font=("Segoe UI", 12, "bold"), text_color="#FDE68A").pack(pady=4)
        
        h_termine = ctk.CTkFrame(right_frame, fg_color="#064E3B", corner_radius=8, border_width=1, border_color="#059669")
        h_termine.grid(row=0, column=2, sticky="ew", padx=8, pady=(10, 6), ipady=4)
        ctk.CTkLabel(h_termine, text="✅ TERMINÉ SUR CE POSTE", font=("Segoe UI", 12, "bold"), text_color="#A7F3D0").pack(pady=4)
        
        # Listes avec style industriel sombre
        def create_kanban_list(parent, col):
            f = ctk.CTkFrame(parent, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
            f.grid(row=1, column=col, sticky="nsew", padx=8, pady=(0, 10))
            sb = ttk.Scrollbar(f, orient="vertical")
            lb = tk.Listbox(f, bg="#1E293B", fg="#F8FAFC", selectbackground="#2563EB", selectforeground="#FFFFFF",
                            highlightthickness=0, bd=0, relief="flat", font=("Segoe UI", 11), yscrollcommand=sb.set)
            sb.config(command=lb.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            return lb
            
        self.list_attente = create_kanban_list(right_frame, 0)
        self.list_encours = create_kanban_list(right_frame, 1)
        self.list_termine = create_kanban_list(right_frame, 2)

    def refresh_be_charge(self):
        cursor = self.db_conn.cursor()
        for item in self.tree_machines.get_children():
            self.tree_machines.delete(item)
            
        cursor.execute("SELECT CodPost, DesPost FROM Postes ORDER BY CodPost")
        for codpost, lib in cursor.fetchall():
            self.tree_machines.insert("", "end", iid=codpost, values=(f"{codpost} - {lib}",))
            
        self.list_attente.delete(0, tk.END)
        self.list_encours.delete(0, tk.END)
        self.list_termine.delete(0, tk.END)

    def on_machine_select(self, event):
        self._update_selection_tags(self.tree_machines)
        
        selected = self.tree_machines.selection()
        if not selected: return
        codpost = selected[0]
        
        self.list_attente.delete(0, tk.END)
        self.list_encours.delete(0, tk.END)
        self.list_termine.delete(0, tk.END)
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT RefOp FROM Postes WHERE CodPost = ?", (codpost,))
        row = cursor.fetchone()
        if not row: return
        ref_op = row[0]
        
        cursor.execute('''
            SELECT CdeDetail.CDE, CdeDetail.ID_OF, CdeDetail.DESIGN, CdeDetail.Qte, OF_Gammes.Poste_Assigne
            FROM OF_Gammes
            JOIN CdeDetail ON OF_Gammes.ID_OF = CdeDetail.ID_OF
            WHERE OF_Gammes.CodeOp = ?
        ''', (ref_op,))
        ofs = cursor.fetchall()
        
        for of in ofs:
            cde, id_of, design, qte, poste_assigne = of
            
            if poste_assigne and poste_assigne != codpost:
                continue
                
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                WHERE ID_OF = ? AND Poste = ?
            ''', (id_of, codpost))
            scans = cursor.fetchone()[0]
            
            txt = f"{id_of} (CDE {cde}) - {design} - {scans}/{qte}"
            
            if scans == 0:
                self.list_attente.insert(tk.END, txt)
            elif scans >= qte:
                self.list_termine.insert(tk.END, txt)
            else:
                self.list_encours.insert(tk.END, txt)


    def _update_single_cmd_in_tree(self, do_piece):
        scanned, total, pct_str = self.get_order_progress(do_piece)
        if self.tree_cmd.exists(do_piece):
            tag = "pas_demarre"
            if total > 0:
                if scanned >= total:
                    tag = "terminee"
                elif scanned > 0:
                    tag = "encours"
            row_vals = self.tree_cmd.item(do_piece, "values")
            if len(row_vals) >= 4:
                self.tree_cmd.item(do_piece, values=(row_vals[0], row_vals[1], row_vals[2], f"{scanned}/{total} ({pct_str})"), tags=(tag,))

    def update_lines_view(self, do_piece):
        open_states = {}
        for item in self.tree_lignes.get_children():
            open_states[item] = self.tree_lignes.item(item, "open")
            self.tree_lignes.delete(item)
            
        mon_op = self.get_mon_op()
        if not mon_op: return
        
        # Pre-fetch sage lines for this order
        lignes_cmd = self.sage_data.get('lignes_par_piece', {}).get(do_piece, [])
        lignes_dict = {key: ligne for key, ligne in lignes_cmd}
        
        cursor = self.db_conn.cursor()
        try:
            cursor.execute("SELECT ID_OF, PROD, DESIGN, OBSERV, Qte, LignesSage FROM CdeDetail WHERE CDE = ?", (do_piece,))
            ofs = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor.execute("SELECT ID_OF, PROD, DESIGN, OBSERV, Qte FROM CdeDetail WHERE CDE = ?", (do_piece,))
            ofs = [list(r) + [""] for r in cursor.fetchall()]
        
        for of in ofs:
            id_of, prod, design, observ, qte, lignes_sage = of
            
            # Fetch routing
            cursor.execute("SELECT CodeOp, Poste_Assigne FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (id_of,))
            routing = cursor.fetchall()
            
            # Find my position in routing
            my_index = -1
            codpost = self.poste_actuel.split(" - ")[0]
            for i, step in enumerate(routing):
                if step[0] == mon_op:
                    # step[1] is Poste_Assigne
                    if step[1] is None or step[1] == codpost:
                        my_index = i
                        break
                    
            if my_index == -1:
                continue # This OF doesn't pass through my operation
                
            # Calculate scans for previous step
            if my_index > 0:
                prev_op = routing[my_index - 1][0]
                # How many of this OF have been processed at ANY poste of prev_op?
                cursor.execute('''
                    SELECT COUNT(*) FROM Scans 
                    JOIN Postes ON Scans.Poste = Postes.CodPost 
                    WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
                ''', (id_of, prev_op))
                scans_prec = cursor.fetchone()[0]
            else:
                scans_prec = qte
                
            # Calculate my scans
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
            ''', (id_of, mon_op))
            mes_scans = cursor.fetchone()[0]
            
            dispo = scans_prec - mes_scans
            
            statut_txt = "À faire"
            situation = ""
            tag = ""
            
            if mes_scans >= qte and qte > 0:
                statut_txt = "Terminé"
                situation = "✅ Terminé à ce poste"
                tag = "terminee"
            elif mes_scans > 0:
                statut_txt = f"En cours ({mes_scans}/{qte})"
                tag = "encours"
                if dispo > 0:
                    situation = f"▶️ Prêt à produire : {dispo} dispo"
                else:
                    situation = f"En attente étape précédente"
            else:
                statut_txt = "Pas démarré"
                tag = "pas_demarre"
                if dispo > 0:
                    situation = f"▶️ Prêt à produire : {dispo} dispo"
                else:
                    situation = "Bloqué (Étape précédente non finie)"
                
            dim = observ if observ else "--"
            self.tree_lignes.insert("", "end", iid=id_of, values=("OF", prod, design, dim, qte, statut_txt, situation), tags=(tag,), open=False)
            
            if lignes_sage:
                lignes_keys = lignes_sage.split(",")
                
                # Get general scans (Child_Key IS NULL)
                cursor.execute('''
                    SELECT COUNT(*) FROM Scans 
                    JOIN Postes ON Scans.Poste = Postes.CodPost 
                    WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key IS NULL
                ''', (id_of, mon_op))
                general_scans = cursor.fetchone()[0]
                scans_restants = general_scans
                
                for l_key in lignes_keys:
                    l_key = l_key.strip()
                    ligne_data = lignes_dict.get(l_key) or lignes_dict.get(f"{do_piece}-{l_key}")
                    if ligne_data:
                        dl_ligne = ligne_data.get("DL_Ligne", "")
                        ref = ligne_data.get("AR_Ref", "")
                        des_sage = ligne_data.get("DL_Design", "")
                        longueur = ligne_data.get("LONG", "")
                        largeur = ligne_data.get("LARG", "")
                        l_dim = f"{longueur}x{largeur}" if longueur and largeur else ""
                        try:
                            l_qte = int(float(str(ligne_data.get("DL_Qte", "1")).replace(',', '.')))
                        except:
                            l_qte = 1
                            
                        # Specific scans for this child
                        cursor.execute('''
                            SELECT COUNT(*) FROM Scans 
                            JOIN Postes ON Scans.Poste = Postes.CodPost 
                            WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key = ?
                        ''', (id_of, mon_op, l_key))
                        specific_scans = cursor.fetchone()[0]
                        
                        l_scans = specific_scans
                        
                        # Pad with general scans if needed
                        missing_for_full = max(0, l_qte - l_scans)
                        if scans_restants > 0 and missing_for_full > 0:
                            if scans_restants >= missing_for_full:
                                l_scans += missing_for_full
                                scans_restants -= missing_for_full
                            else:
                                l_scans += scans_restants
                                scans_restants = 0
                                
                        if l_scans >= l_qte and l_qte > 0:
                            c_tag = "terminee"
                            c_statut = "Terminé"
                        elif l_scans > 0:
                            c_tag = "encours"
                            c_statut = f"En cours ({l_scans}/{l_qte})"
                        else:
                            c_tag = "pas_demarre"
                            c_statut = "Pas encore démarré"
                            
                        # Insert as child
                        child_iid = f"{id_of}_{l_key}"
                        self.tree_lignes.insert(id_of, "end", iid=child_iid, values=(f"↳ Ligne {dl_ligne}", ref, des_sage, l_dim, l_qte, c_statut, ""), tags=(c_tag,))
                        
        # Restore open states
        for item, is_open in open_states.items():
            if self.tree_lignes.exists(item):
                self.tree_lignes.item(item, open=is_open)
                        
        # Tag child handled earlier
    def _update_selection_tags(self, tree):
        selected_items = tree.selection()
        
        # Traverse all items (parent + children depth 1)
        all_items = []
        for item in tree.get_children():
            all_items.append(item)
            all_items.extend(tree.get_children(item))
            
        for item in all_items:
            tags = tree.item(item, "tags")
            if not tags:
                # Add default_sel if there's no tag but it's selected
                if item in selected_items:
                    tree.item(item, tags=("default_sel",))
                continue
                
            base_tag = tags[0].replace("_sel", "")
            new_tag = f"{base_tag}_sel" if item in selected_items else base_tag
            
            if tags[0] != new_tag:
                tree.item(item, tags=(new_tag,))

    def on_order_select(self, event):
        self._update_selection_tags(self.tree_cmd)
        
        selected = self.tree_cmd.selection()
        if not selected:
            return
        
        do_piece = selected[0]
        
        # Mettre à jour l'en-tête
        entete = self.sage_data['entetes'].get(do_piece, {})
        client = entete.get("DO_Tiers", "Inconnu")
        self.lbl_commande.configure(text=f"Commande : {do_piece}")
        self.lbl_client.configure(text=f"Client : {client}")
        
        self.lbl_lignes_title.configure(text=f"ARTICLES DE LA COMMANDE : {do_piece}")
        self.update_lines_view(do_piece)
        
        children = self.tree_lignes.get_children()
        if children:
            self.tree_lignes.selection_set(children[0])
            self.tree_lignes.see(children[0])
            self.on_article_select()
        else:
            # Clear timeline if no articles
            for widget in self.timeline_frame.winfo_children():
                if widget != self.timeline_frame.winfo_children()[0]: # Keep title
                    widget.destroy()
            self.lbl_article_details.configure(text="Aucun article à produire pour ce poste sur cette commande.")
            self.show_timeline()
            
        self.scan_entry.focus_set()


    def on_article_select(self, event=None, force_show=True):
        self._update_selection_tags(self.tree_lignes)
        
        if getattr(self, '_is_scanning', False):
            force_show = False
            
        selected = self.tree_lignes.selection()
        if not selected:
            return
            
        key = selected[0] # This is ID_OF now
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT PROD, DESIGN, OBSERV, Qte FROM CdeDetail WHERE ID_OF = ?", (key,))
        of_data = cursor.fetchone()
        if not of_data: return
        
        prod, design, observ, qte = of_data
        dim = observ if observ else "--"
        
        self.lbl_article_details.configure(text=f"OF: {key} - {prod} - {design}\\nDimensions : {dim} | Qté: {qte}")
        
        # Reconstruire dynamiquement la timeline pour CET OF
        for widget in self.timeline_frame.winfo_children():
            if widget != self.timeline_frame.winfo_children()[0]: # Keep the title
                widget.destroy()
                
        self.timeline_blocks = {}
        timeline_container = ctk.CTkFrame(self.timeline_frame, fg_color="transparent")
        timeline_container.pack(expand=True, fill=tk.BOTH, padx=12, pady=(0, 10))
        
        cursor.execute("SELECT CodeOp FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (key,))
        routing = cursor.fetchall()
        
        mon_op = self.get_mon_op()
        for (op,) in routing:
            # Fetch operation name
            cursor.execute("SELECT LibelOp FROM Operations WHERE RefOp = ?", (op,))
            op_row = cursor.fetchone()
            op_name = op_row[0] if op_row else f"{op} (Non défini)"
            
            # Count total scans for this operation for this OF
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
            ''', (key, op))
            count = cursor.fetchone()[0]
            
            is_current = (op == mon_op)
            is_done = (count >= qte and qte > 0)
            
            if is_current:
                card_bg = "#162032"
                border_c = "#2563EB"
                border_w = 2
                title_c = "#38BDF8"
                count_c = "#34D399" if is_done else "#38BDF8"
            elif is_done:
                card_bg = "#064E3B"
                border_c = "#059669"
                border_w = 1
                title_c = "#A7F3D0"
                count_c = "#FFFFFF"
            else:
                card_bg = "#1E293B"
                border_c = "#334155"
                border_w = 1
                title_c = "#94A3B8"
                count_c = "#F8FAFC"
                
            block = ctk.CTkFrame(timeline_container, fg_color=card_bg, corner_radius=10, border_width=border_w, border_color=border_c)
            block.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=3, pady=4)
            
            lbl_nom = ctk.CTkLabel(block, text=op_name, font=("Segoe UI", 11, "bold"), text_color=title_c, wraplength=95)
            lbl_nom.pack(pady=(8, 0))
            
            lbl_count = ctk.CTkLabel(block, text=f"{count} / {qte}", font=("Segoe UI", 20, "bold"), text_color=count_c)
            lbl_count.pack(expand=True, pady=4)
                
        if force_show:
            self.show_timeline()

    def show_timeline(self):
        self.scan_flash_frame.place_forget()
        self.timeline_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    def on_scan(self, event):
        qr_text = self.scan_var.get().strip()
        self.scan_var.set("")
        if not qr_text: return
        self.process_scan(qr_text)

    def open_scan_simulator(self):
        selected = self.tree_lignes.selection()
        if not selected:
            messagebox.showwarning("Simulateur", "Veuillez d'abord sélectionner un OF dans la liste de gauche.")
            return
            
        key = selected[0]
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT CDE, PROD, DESIGN, OBSERV, Qte FROM CdeDetail WHERE ID_OF = ?", (key,))
        of_data = cursor.fetchone()
        
        if not of_data:
            return
            
        cde, prod, designation, observ, qte = of_data
        dim = observ if observ else "--"
        barcode = key # The QR code is just the ID_OF (e.g., "OF-1000")
        
        sim_win = ctk.CTkToplevel(self.root)
        sim_win.title("Simulateur de Douchette")
        sim_win.geometry("480x320")
        sim_win.configure(fg_color="#0B1120")
        
        card = ctk.CTkFrame(sim_win, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#334155")
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        
        ctk.CTkLabel(card, text="🔫 SIMULATEUR DOUCHETTE ATELIER", font=("Segoe UI", 14, "bold"), text_color="#38BDF8").pack(pady=(16, 8))
        
        info_frame = ctk.CTkFrame(card, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=6)
        
        ctk.CTkLabel(info_frame, text=f"Désignation : {designation}", font=("Segoe UI", 12, "bold"), text_color="#F8FAFC", wraplength=380, justify="left").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(info_frame, text=f"Réf : {prod}  |  Dimensions : {dim}", font=("Segoe UI", 11), text_color="#94A3B8").pack(anchor="w", padx=12, pady=2)
        
        bc_frame = ctk.CTkFrame(info_frame, fg_color="#162032", corner_radius=8, border_width=1, border_color="#2563EB")
        bc_frame.pack(fill=tk.X, padx=12, pady=(8, 10))
        ctk.CTkLabel(bc_frame, text=f"Code-Barres : {barcode}", font=("Segoe UI", 15, "bold"), text_color="#38BDF8").pack(pady=6)
        
        def do_scan():
            self.process_scan(barcode)
            sim_win.destroy()
            
        ctk.CTkButton(card, text="⚡ Valider le Scan de l'OF", font=("Segoe UI", 13, "bold"), 
                      fg_color="#059669", hover_color="#047857", text_color="white", 
                      height=38, corner_radius=8, command=do_scan).pack(fill=tk.X, padx=16, pady=(8, 14))

    def process_scan(self, qr_code):
        qr_code = qr_code.strip()
        
        # LOGIQUE DE COMMANDE (CMD-...)
        if qr_code.startswith("CMD-"):
            do_piece = qr_code[4:] # On retire 'CMD-'
            
            entete = self.sage_data['entetes'].get(do_piece)
            if not entete:
                self.load_sage_data()
                entete = self.sage_data['entetes'].get(do_piece)
                
            if not entete:
                self.update_status_bar("error", f"ERREUR : Commande {do_piece} introuvable")
                return
                
            client = entete.get("DO_Tiers", "Inconnu")
            
            # Mettre à jour l'interface
            self.lbl_commande.configure(text=f"Commande : {do_piece}")
            self.lbl_client.configure(text=f"Client : {client}")
            self.lbl_designation.configure(text="Désignation : --")
            self.lbl_dim.configure(text="DIMENSIONS\n-- x --")
            self.lbl_progression.configure(text="0 / 0")
            
            # Sélection dans l'arbre pour charger les articles
            if self.tree_cmd.exists(do_piece):
                self.tree_cmd.selection_set(do_piece)
                self.tree_cmd.see(do_piece)
                self.on_order_select(None)
            else:
                self.lbl_lignes_title.configure(text=f"ARTICLES DE LA COMMANDE : {do_piece}")
                self.update_lines_view(do_piece)
                
                # Auto-select the first article even if cmd is not in tree_cmd
                children = self.tree_lignes.get_children()
                if children:
                    self.tree_lignes.selection_set(children[0])
                    self.tree_lignes.see(children[0])
                    self.on_article_select()
                else:
                    for widget in self.timeline_frame.winfo_children():
                        if widget != self.timeline_frame.winfo_children()[0]:
                            widget.destroy()
                    self.lbl_article_details.configure(text="Aucun article à produire pour ce poste sur cette commande.")
                    self.show_timeline()
            
            self.update_status_bar("success", f"Commande {do_piece} chargée.")
            return


        # LOGIQUE D'ARTICLE (ART-...)
        if qr_code.startswith("OF-"):
            key = qr_code
        elif qr_code.startswith("ART-"):
            # Format: ART-BC12345-1000
            parts = qr_code[4:].rsplit("-", 1)
            if len(parts) != 2:
                self.update_status_bar("error", "ERREUR: Format Article non reconnu")
                return
                
            do_piece, dl_ligne = parts[0], parts[1]
            key = f"{do_piece}-{dl_ligne}"
        else:
            # Rétrocompatibilité
            if "-" not in qr_code:
                key = qr_code
            else:
                parts = qr_code.rsplit("-", 1)
                do_piece, dl_ligne = parts[0], parts[1]
                key = f"{do_piece}-{dl_ligne}"
            
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT CDE, PROD, DESIGN, Qte, OBSERV FROM CdeDetail WHERE ID_OF = ?", (key,))
        of_data = cursor.fetchone()
        
        if not of_data:
            self.update_status_bar("error", f"ERREUR : Code-barres inconnu ({qr_code})")
            return
            
        do_piece, prod, designation, qte_totale, observ = of_data
        client = "Inconnu" # We could fetch it from sage_data
        try:
            entete = self.sage_data['entetes'].get(do_piece, {})
            client = entete.get("DO_Tiers", "Inconnu")
        except: pass
        
        # Count my scans
        mon_op = self.get_mon_op()
        cursor.execute('''
            SELECT COUNT(*) FROM Scans 
            JOIN Postes ON Scans.Poste = Postes.CodPost 
            WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
        ''', (key, mon_op))
        scans_actuels = cursor.fetchone()[0]
        
        if scans_actuels >= qte_totale:
            self.update_status_bar("error", f"ERREUR : Quantité dépassée pour cet OF ({scans_actuels}/{qte_totale})")
        else:
            # Insertion en base
            codpost = self.poste_actuel.split(" - ")[0]
            cursor.execute("INSERT INTO Scans (ID_OF, Poste) VALUES (?, ?)", (key, codpost))
            self.db_conn.commit()
            
            nouveau_count = scans_actuels + 1
            
            # Rafraîchir dynamiquement le tableau Kanban
            self.update_lines_view(do_piece)
            
            # Rafraîchir dynamiquement la commande globale
            self._update_single_cmd_in_tree(do_piece)
            
            # Mettre à jour les infos du flash
            self.lbl_commande.configure(text=f"Commande : {do_piece}")
            self.lbl_client.configure(text=f"Client : {client}")
            self.lbl_designation.configure(text=f"Désignation : {designation}")
            dim_text = observ if observ else "--"
            self.lbl_dim.configure(text=f"OF : {key}\\nDimensions : {dim_text}")
            self.lbl_progression.configure(text=f"{nouveau_count} / {qte_totale}")
            
            # Afficher le flash
            self.timeline_frame.place_forget()
            self.scan_flash_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            
            # Select
            self._is_scanning = True
            if self.tree_lignes.exists(key):
                self.tree_lignes.selection_set(key)
                self.tree_lignes.see(key)
            self._is_scanning = False
                
            if hasattr(self, '_flash_timer'):
                self.root.after_cancel(self._flash_timer)
            self._flash_timer = self.root.after(4000, self.show_timeline)
            
            if nouveau_count == qte_totale:
                self.update_status_bar("success", f"OK : OF terminé à ce poste ! ({designation})")
            else:
                self.update_status_bar("progress", f"OK : Pièce enregistrée ({designation})")

    def _add_scans_with_catchup(self, key, mon_op, codpost, amount_to_add, qte_totale, child_key=None):
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT CodeOp, Poste_Assigne FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (key,))
        routing = cursor.fetchall()
        
        for i, step in enumerate(routing):
            prev_op, poste_assigne = step
            if prev_op == mon_op:
                break
                
            if child_key:
                cursor.execute('''
                    SELECT COUNT(*) FROM Scans 
                    JOIN Postes ON Scans.Poste = Postes.CodPost 
                    WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key = ?
                ''', (key, prev_op, child_key))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM Scans 
                    JOIN Postes ON Scans.Poste = Postes.CodPost 
                    WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key IS NULL
                ''', (key, prev_op))
                
            prev_total_scans = cursor.fetchone()[0]
            target_total_scans = prev_total_scans + amount_to_add
            
            missing = amount_to_add
            if missing > 0:
                poste_to_use = poste_assigne
                if not poste_to_use:
                    cursor.execute("SELECT CodPost FROM Postes WHERE RefOp = ? LIMIT 1", (prev_op,))
                    row = cursor.fetchone()
                    poste_to_use = row[0] if row else None
                    
                if poste_to_use:
                    for _ in range(missing):
                        if child_key:
                            cursor.execute("INSERT INTO Scans (ID_OF, Poste, Child_Key) VALUES (?, ?, ?)", (key, poste_to_use, child_key))
                        else:
                            cursor.execute("INSERT INTO Scans (ID_OF, Poste) VALUES (?, ?)", (key, poste_to_use))
        
        added = 0
        for _ in range(amount_to_add):
            if child_key:
                cursor.execute("INSERT INTO Scans (ID_OF, Poste, Child_Key) VALUES (?, ?, ?)", (key, codpost, child_key))
            else:
                cursor.execute("INSERT INTO Scans (ID_OF, Poste) VALUES (?, ?)", (key, codpost))
            added += 1
            
        self.db_conn.commit()
        return added

    def manual_scan(self, amount):
        selected = self.tree_lignes.selection()
        if not selected:
            messagebox.showwarning("Erreur", "Veuillez d'abord sélectionner un article.")
            return
        
        original_selection = selected[0]
        key = original_selection
        child_key = None
        
        if "_" in key:
            parent_id = self.tree_lignes.parent(key)
            if not parent_id: return
            child_key = key.split("_", 1)[1]
            key = parent_id
                
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT CDE, Qte FROM CdeDetail WHERE ID_OF = ?", (key,))
        of_data = cursor.fetchone()
        if not of_data: return
        
        do_piece, qte_totale = of_data
        mon_op = self.get_mon_op()
        codpost = self.poste_actuel.split(" - ")[0]
        
        if child_key is not None:
            lignes_dict = {k: v for k, v in self.sage_data.get('lignes_par_piece', {}).get(do_piece, [])}
            c_data = lignes_dict.get(child_key, {})
            try:
                target_qte = int(float(str(c_data.get("DL_Qte", "1")).replace(',', '.')))
            except:
                target_qte = 1
                
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key = ?
            ''', (key, mon_op, child_key))
            scans_actuels_specific = cursor.fetchone()[0]
        else:
            target_qte = qte_totale
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key IS NULL
            ''', (key, mon_op))
            scans_actuels_specific = cursor.fetchone()[0]
        
        if scans_actuels_specific >= target_qte:
            messagebox.showinfo("Info", "La quantité max est déjà atteinte pour cet élément à ce poste.")
            return
            
        to_add = 0
        if amount == "all":
            to_add = target_qte - scans_actuels_specific
        else:
            to_add = amount
            
        if to_add <= 0:
            return
            
        if scans_actuels_specific + to_add > target_qte:
            to_add = target_qte - scans_actuels_specific
            
        added = self._add_scans_with_catchup(key, mon_op, codpost, to_add, qte_totale, child_key=child_key)
        if added <= 0: return
        
        self.update_lines_view(do_piece)
        if hasattr(self, "_update_single_cmd_in_tree"):
                self._update_single_cmd_in_tree(do_piece)
                
        if self.tree_lignes.exists(original_selection):
            self.tree_lignes.selection_set(original_selection)
            self.tree_lignes.see(original_selection)
            self.on_article_select(None)
            
        self.update_status_bar("success", f"{to_add} scan(s) ajouté(s) manuellement.")

    def manual_unscan(self, amount):
        selected = self.tree_lignes.selection()
        if not selected:
            messagebox.showwarning("Erreur", "Veuillez d'abord sélectionner un article.")
            return
        
        original_selection = selected[0]
        key = original_selection
        child_key = None
        
        if "_" in key:
            parent_id = self.tree_lignes.parent(key)
            if not parent_id: return
            child_key = key.split("_", 1)[1]
            key = parent_id
                
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT CDE FROM CdeDetail WHERE ID_OF = ?", (key,))
        of_data = cursor.fetchone()
        if not of_data: return
        
        do_piece = of_data[0]
        mon_op = self.get_mon_op()
        
        if child_key is not None:
            cursor.execute('''
                SELECT Scans.ID_Scan FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key = ?
                ORDER BY Scans.ID_Scan DESC
            ''', (key, mon_op, child_key))
            scans = cursor.fetchall()
            
            if not scans:
                cursor.execute('''
                    SELECT Scans.ID_Scan FROM Scans 
                    JOIN Postes ON Scans.Poste = Postes.CodPost 
                    WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND Scans.Child_Key IS NULL
                    ORDER BY Scans.ID_Scan DESC
                ''', (key, mon_op))
                scans = cursor.fetchall()
                
            lignes_dict = {k: v for k, v in self.sage_data.get('lignes_par_piece', {}).get(do_piece, [])}
            c_data = lignes_dict.get(child_key, {})
            try:
                target_qte = int(float(str(c_data.get("DL_Qte", "1")).replace(',', '.')))
            except:
                target_qte = 1
        else:
            cursor.execute('''
                SELECT Scans.ID_Scan FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
                ORDER BY Scans.ID_Scan DESC
            ''', (key, mon_op))
            scans = cursor.fetchall()
            target_qte = len(scans)
            
        if not scans:
            messagebox.showinfo("Info", "Aucun scan à annuler pour cet article à ce poste.")
            return
            
        to_remove = min(len(scans), target_qte) if amount == "all" else amount
        
        for i in range(min(to_remove, len(scans))):
            id_scan = scans[i][0]
            cursor.execute("DELETE FROM Scans WHERE ID_Scan = ?", (id_scan,))
            
        self.db_conn.commit()
        
        self.update_lines_view(do_piece)
        if hasattr(self, "_update_single_cmd_in_tree"):
                self._update_single_cmd_in_tree(do_piece)
                
        if self.tree_lignes.exists(original_selection):
            self.tree_lignes.selection_set(original_selection)
            self.tree_lignes.see(original_selection)
            self.on_article_select(None)
            
        self.update_status_bar("success", f"{min(to_remove, len(scans))} scan(s) annulé(s) manuellement.")

if __name__ == "__main__":
    import traceback
    try:
        root = ctk.CTk()
        app = SotraglaceApp(root)
        root.mainloop()
    except Exception as e:
        with open("crash.log", "w") as f:
            f.write(traceback.format_exc())


