import os
import sys
import json
import sqlite3
import csv
import tkinter as tk
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
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT CodPost, DesPost FROM Postes")
        postes = [f"{row[0]} - {row[1]}" for row in cursor.fetchall()]
        conn.close()
        return postes if postes else ["Erreur - Aucun poste"]
    except Exception:
        return ["Erreur BD"]

class ConfigDialog(tk.Toplevel):
    def __init__(self, parent, is_cancellable=False):
        super().__init__(parent)
        self.is_cancellable = is_cancellable
        self.title("Configuration du Poste")
        self.geometry("500x250")
        self.poste_choisi = tk.StringVar()
        self.result = None
        
        self.grab_set()
        
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        tk.Label(self, text="Veuillez choisir le poste de travail :", 
                 font=("Helvetica", 14, "bold")).pack(pady=20)
        
        postes_list = get_postes_disponibles()
        self.cb = ttk.Combobox(self, textvariable=self.poste_choisi, values=postes_list, font=("Helvetica", 14), state="readonly")
        self.cb.pack(pady=10, fill=tk.X, padx=50)
        if postes_list:
            self.cb.current(0)
            
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Valider", font=("Helvetica", 14, "bold"), 
                  bg="#4CAF50", fg="white", command=self.on_validate).pack(side=tk.LEFT, padx=10)
        
        if self.is_cancellable:
            tk.Button(btn_frame, text="Annuler", font=("Helvetica", 14), 
                      bg="#F44336", fg="white", command=self.on_close).pack(side=tk.LEFT, padx=10)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def on_validate(self):
        if self.poste_choisi.get():
            self.result = self.poste_choisi.get()
            self.destroy()
            
    def on_close(self):
        self.destroy()
        if not self.is_cancellable:
            sys.exit(0)

class AddOfDialog(tk.Toplevel):
    def __init__(self, parent, db_conn, cde, default_qte=1, default_design="", default_obs="", lignes_sage=""):
        super().__init__(parent)
        self.title(f"Ajouter un Produit (OF) à la commande {cde}")
        self.geometry("700x700")
        self.configure(bg="#2D2D30")
        self.db_conn = db_conn
        self.cde = cde
        self.lignes_sage = lignes_sage
        self.result = False
        
        # UI
        tk.Label(self, text=f"NOUVEL ORDRE DE FABRICATION\nCommande : {cde}", font=("Arial", 14, "bold"), bg="#2D2D30", fg="white").pack(pady=10)
        
        self.btn_frame = tk.Frame(self, bg="#2D2D30")
        self.btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        form_frame = tk.Frame(self, bg="#2D2D30")
        form_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Produit
        tk.Label(form_frame, text="Produit :", font=("Arial", 12), bg="#2D2D30", fg="white").grid(row=0, column=0, sticky="w", pady=5)
        
        self.prod_var = tk.StringVar()
        self.cb_prod = ttk.Combobox(form_frame, textvariable=self.prod_var, state="readonly", width=40, font=("Arial", 11))
        self.cb_prod.grid(row=0, column=1, sticky="w", pady=5)
        self.cb_prod.bind("<<ComboboxSelected>>", self.on_prod_select)
        
        # Charger les produits
        self.produits_map = {}
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT RefProd, DesProd FROM Produits")
        for row in cursor.fetchall():
            display = f"{row[0]} - {row[1]}"
            self.produits_map[display] = (row[0], row[1])
        self.cb_prod['values'] = list(self.produits_map.keys())
        
        # Designation
        tk.Label(form_frame, text="Désignation :", font=("Arial", 12), bg="#2D2D30", fg="white").grid(row=1, column=0, sticky="w", pady=5)
        self.design_var = tk.StringVar(value=default_design)
        tk.Entry(form_frame, textvariable=self.design_var, font=("Arial", 11), width=42).grid(row=1, column=1, sticky="w", pady=5)
        
        # Observations
        tk.Label(form_frame, text="Observations :", font=("Arial", 12), bg="#2D2D30", fg="white").grid(row=2, column=0, sticky="w", pady=5)
        self.obs_var = tk.StringVar(value=default_obs)
        tk.Entry(form_frame, textvariable=self.obs_var, font=("Arial", 11), width=42).grid(row=2, column=1, sticky="w", pady=5)
        
        # Quantite
        tk.Label(form_frame, text="Quantité :", font=("Arial", 12), bg="#2D2D30", fg="white").grid(row=3, column=0, sticky="w", pady=5)
        self.qte_var = tk.IntVar(value=default_qte)
        tk.Spinbox(form_frame, from_=1, to=9999, textvariable=self.qte_var, font=("Arial", 11), width=10).grid(row=3, column=1, sticky="w", pady=5)
        
        # Gamme Preview avec choix des postes
        tk.Label(form_frame, text="Gamme & Assignation des Postes :", font=("Arial", 12, "bold"), bg="#2D2D30", fg="#4da6ff").grid(row=4, column=0, columnspan=2, sticky="w", pady=(15,5))
        
        self.gamme_frame = tk.Frame(form_frame, bg="#1E1E1E", bd=1, relief="sunken")
        self.gamme_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=5)
        self.gamme_vars = []

        # Boutons
        tk.Button(self.btn_frame, text="Annuler", bg="#F44336", fg="white", font=("Arial", 11, "bold"), width=15, command=self.destroy).pack(side=tk.RIGHT, padx=20)
        tk.Button(self.btn_frame, text="Créer l'OF", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=15, command=self.save).pack(side=tk.RIGHT, padx=10)
        
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
                tk.Label(self.gamme_frame, text="Aucune gamme définie pour ce produit.", bg="#1E1E1E", fg="white").pack(pady=10)
                return
                
            for step in gammes:
                ordre, code_op, libel_op = step
                libel_op = libel_op if libel_op else "Opération sans libellé"
                
                row_frame = tk.Frame(self.gamme_frame, bg="#1E1E1E")
                row_frame.pack(fill=tk.X, padx=10, pady=5)
                
                var_check = tk.BooleanVar(value=False)
                
                # Chercher les postes compatibles
                cursor.execute("SELECT CodPost, DesPost FROM Postes WHERE RefOp = ?", (code_op,))
                postes_compatibles = ["Libre (N'importe lequel)"] + [f"{r[0]} - {r[1]}" for r in cursor.fetchall()]
                
                var_poste = tk.StringVar(value=postes_compatibles[0])
                cb_poste = ttk.Combobox(row_frame, textvariable=var_poste, values=postes_compatibles, state="disabled", width=30)
                
                def on_check_toggle(v=var_check, c=cb_poste):
                    if v.get():
                        c.config(state="readonly")
                    else:
                        c.config(state="disabled")
                        
                chk = tk.Checkbutton(row_frame, text=libel_op, variable=var_check, command=on_check_toggle, bg="#1E1E1E", fg="#4da6ff", selectcolor="#2D2D30", font=("Arial", 11, "bold"), width=20, anchor="w")
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
        self.root.after(100, lambda: self.root.state('zoomed'))
        
        # Style global
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configuration des Treeview
        self.style.configure("Treeview", 
                             background="#333333", foreground="white", 
                             fieldbackground="#333333", rowheight=40, font=("Segoe UI", 12))
        self.style.configure("Treeview.Heading", 
                             background="#444444", foreground="white", 
                             font=("Segoe UI", 12, "bold"))
        self.style.map("Treeview", background=[], foreground=[])
        
        # Couleurs des statuts
        self.style.configure("TFrame", background="#1E1E1E")
        self.root.configure(bg="#1E1E1E")
        
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
        if self.root.focus_get() not in (self.scan_entry, self.search_entry):
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
        
        # Upgrade schema if LignesSage doesn't exist
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
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
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
        return 'latin-1'

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
        # Création du système d'onglets (Notebook)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill=tk.BOTH)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_main_tab_changed)
        
        # Onglet 1 : Atelier
        self.tab_atelier = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab_atelier, text="⚙️ ATELIER (Production)")
        
        # Onglet 2 : Bureau d'Étude
        self.tab_be = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab_be, text="📐 BUREAU D'ÉTUDE (Nomenclatures)")
        
        # Construction de l'interface Atelier dans tab_atelier
        # 1. Header (Bandeau supérieur)
        self.header_frame = tk.Frame(self.tab_atelier, bg="#2C3E50", height=80)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)
        self.header_frame.pack_propagate(False)
        
        self.lbl_title = tk.Label(self.header_frame, text=f"POSTE : {self.poste_nom_court.upper()}", 
                                  font=("Arial", 24, "bold"), fg="white", bg="#2C3E50")
        self.lbl_title.pack(side=tk.LEFT, padx=20, pady=15)
        
        btn_poste = tk.Button(self.header_frame, text="⚙️ Changer de Poste", font=("Segoe UI", 12),
                              bg="#FF9800", fg="white", relief=tk.FLAT, command=self.change_poste)
        btn_poste.pack(side=tk.RIGHT, padx=10, pady=20)
        
        btn_refresh = tk.Button(self.header_frame, text="🔄 Actualiser CSV", font=("Segoe UI", 12),
                                bg="#4CAF50", fg="white", relief=tk.FLAT, command=self.action_refresh)
        btn_refresh.pack(side=tk.RIGHT, padx=10, pady=20)
        
        btn_simu = tk.Button(self.header_frame, text="🔫 Test Scan", font=("Segoe UI", 12),
                             bg="#9C27B0", fg="white", relief=tk.FLAT, command=self.open_scan_simulator)
        btn_simu.pack(side=tk.RIGHT, padx=10, pady=20)

        # 2. Body (Zone centrale)
        self.body_frame = tk.Frame(self.tab_atelier, bg="#1E1E1E")
        self.body_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.body_frame.columnconfigure(0, weight=6) # Gauche 60%
        self.body_frame.columnconfigure(1, weight=4) # Droite 40%
        self.body_frame.rowconfigure(0, weight=1)
        
        # --- BLOC DROIT (Vue Globale des Commandes) ---
        self.right_col = tk.Frame(self.body_frame, bg="#1E1E1E")
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)
        
        search_frame = tk.Frame(self.right_col, bg="#1E1E1E")
        search_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(search_frame, text="LISTE DES COMMANDES", font=("Segoe UI", 16, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 12), width=15)
        self.search_entry.pack(side=tk.RIGHT)
        tk.Label(search_frame, text="Recherche:", font=("Segoe UI", 12), bg="#1E1E1E", fg="white").pack(side=tk.RIGHT, padx=5)

        cols_cmd = ("commande", "date", "client", "avancement")
        tree_cmd_frame = tk.Frame(self.right_col)
        tree_cmd_frame.pack(expand=True, fill=tk.BOTH)
        
        scroll_cmd = ttk.Scrollbar(tree_cmd_frame, orient="vertical")
        
        self.tree_cmd = ttk.Treeview(tree_cmd_frame, columns=cols_cmd, show="headings", selectmode="browse", yscrollcommand=scroll_cmd.set)
        scroll_cmd.config(command=self.tree_cmd.yview)
        
        self.tree_cmd.heading("commande", text="N° Cmd")
        self.tree_cmd.heading("date", text="Date")
        self.tree_cmd.heading("client", text="Client")
        self.tree_cmd.heading("avancement", text="Prog.")
        
        self.tree_cmd.column("commande", width=100)
        self.tree_cmd.column("date", width=80)
        self.tree_cmd.column("client", width=180)
        self.tree_cmd.column("avancement", width=80, anchor="center")
        
        scroll_cmd.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_cmd.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.tree_cmd.tag_configure('terminee_sel', background='#1E7B35', foreground='white', font=("Segoe UI", 11, "bold underline"))
        self.tree_cmd.tag_configure('encours_sel', background='#A85C1C', foreground='white', font=("Segoe UI", 11, "bold underline"))
        self.tree_cmd.tag_configure('pas_demarre_sel', background='#005A9E', foreground='white', font=("Segoe UI", 11, "bold underline"))
        self.tree_cmd.tag_configure('default_sel', background='#005A9E', foreground='white', font=("Segoe UI", 11, "bold underline"))
        self.tree_cmd.bind("<<TreeviewSelect>>", lambda e: [self._update_selection_tags(self.tree_cmd), self.on_order_select(e)])
        
        self.tree_cmd.tag_configure('terminee', background='#2e5e32')
        self.tree_cmd.tag_configure('encours', background='#825018')
        self.tree_cmd.tag_configure('pas_demarre', background='#424242', foreground='#AAAAAA')
        
        font_sel = ("Segoe UI", 11, "bold underline")
        sel_blue = '#005A9E'
        
        # --- BLOC GAUCHE (Détails de la commande et Focus Scan) ---
        self.left_col = tk.Frame(self.body_frame, bg="#1E1E1E")
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        
        # Détails Commande (Haut)
        cmd_info_frame = tk.Frame(self.left_col, bg="#2D2D30", relief=tk.RAISED, borderwidth=1)
        cmd_info_frame.pack(fill=tk.X, pady=(0, 10), ipady=5)
        
        self.lbl_commande = tk.Label(cmd_info_frame, text="Commande : --", font=("Arial", 16, "bold"), bg="#2D2D30", fg="#4da6ff", anchor="w")
        self.lbl_commande.pack(fill=tk.X, padx=15, pady=2)
        
        self.lbl_client = tk.Label(cmd_info_frame, text="Client : --", font=("Arial", 16), bg="#2D2D30", fg="white", anchor="w")
        self.lbl_client.pack(fill=tk.X, padx=15, pady=2)
        
        # Tableau Articles (Milieu)
        self.lbl_lignes_title = tk.Label(self.left_col, text="ARTICLES DE LA COMMANDE", font=("Segoe UI", 12, "bold"), fg="#CCCCCC", bg="#1E1E1E", anchor="w")
        self.lbl_lignes_title.pack(fill=tk.X, pady=5)
        
        cols_lignes = ("ligne", "ref", "designation", "dim", "qte", "statut", "situation")
        # Changement : selectmode="browse" pour pouvoir cliquer sur un article
        
        tree_lignes_frame = tk.Frame(self.left_col)
        tree_lignes_frame.pack(fill=tk.X, pady=(0, 15))
        
        scroll_lignes = ttk.Scrollbar(tree_lignes_frame, orient="vertical")
        
        self.tree_lignes = ttk.Treeview(tree_lignes_frame, columns=cols_lignes, show="tree headings", selectmode="browse", height=6, yscrollcommand=scroll_lignes.set)
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
        self.tree_lignes.column("ref", width=70)
        self.tree_lignes.column("designation", width=180)
        self.tree_lignes.column("dim", width=160)
        self.tree_lignes.column("qte", width=60, anchor="center")
        self.tree_lignes.column("statut", width=90, anchor="center")
        self.tree_lignes.column("situation", width=150)
        
        scroll_lignes.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_lignes.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.tree_lignes.bind("<<TreeviewSelect>>", lambda e: [self._update_selection_tags(self.tree_lignes), self.on_article_select(e)])        
        self.actions_article_frame = tk.Frame(self.left_col, bg="#1E1E1E")
        self.actions_article_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(self.actions_article_frame, text="Action Manuelle :", font=("Segoe UI", 10, "bold"), fg="white", bg="#1E1E1E").pack(side=tk.LEFT, padx=5)
        
        self.btn_scan_one = tk.Button(self.actions_article_frame, text="+1 Scanner", bg="#1E88E5", fg="white", font=("Arial", 10, "bold"), command=lambda: self.manual_scan(1))
        self.btn_scan_one.pack(side=tk.LEFT, padx=5)
        
        self.btn_scan_all = tk.Button(self.actions_article_frame, text="++ TOUT Scanner", bg="#388E3C", fg="white", font=("Arial", 10, "bold"), command=lambda: self.manual_scan("all"))
        self.btn_scan_all.pack(side=tk.LEFT, padx=5)
        
        self.btn_unscan_one = tk.Button(self.actions_article_frame, text="-1 Descanner", bg="#F57C00", fg="white", font=("Arial", 10, "bold"), command=lambda: self.manual_unscan(1))
        self.btn_unscan_one.pack(side=tk.LEFT, padx=5)
        
        self.btn_unscan_all = tk.Button(self.actions_article_frame, text="-- TOUT Descanner", bg="#D32F2F", fg="white", font=("Arial", 10, "bold"), command=lambda: self.manual_unscan("all"))
        self.btn_unscan_all.pack(side=tk.LEFT, padx=5)
        
        self.tree_lignes.tag_configure('terminee', background='#388E3C', foreground='white')
        self.tree_lignes.tag_configure('encours', background='#F57C00', foreground='white')
        self.tree_lignes.tag_configure('pret', background='#1E88E5', foreground='white')
        self.tree_lignes.tag_configure('attente', background='#424242', foreground='#AAAAAA')
        self.tree_lignes.tag_configure('pas_demarre', background='#424242', foreground='#AAAAAA')
        self.tree_lignes.tag_configure('erreur', background='#D32F2F', foreground='white')
        self.tree_lignes.tag_configure('child', foreground='#888888')
        
        # Variantes de sélection
        font_sel = ("Segoe UI", 11, "bold underline")
        sel_blue = '#005A9E'
        # Uniquement 'terminé' reste vert à la sélection
        self.tree_lignes.tag_configure('terminee_sel', background='#388E3C', foreground='white', font=font_sel) 
        # Les autres prennent le beau bleu de sélection
        self.tree_lignes.tag_configure('encours_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('pret_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('attente_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('pas_demarre_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('erreur_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('child_sel', background=sel_blue, foreground='white', font=font_sel)
        self.tree_lignes.tag_configure('default_sel', background=sel_blue, foreground='white', font=font_sel)

        # Focus Industriel / Radar (Bas gauche)
        self.bottom_left_container = tk.Frame(self.left_col, bg="#1E1E1E")
        self.bottom_left_container.pack(expand=True, fill=tk.BOTH)
        
        # --- FRAME 1 : Le Radar / Frise globale (Affiché par défaut) ---
        self.timeline_frame = tk.Frame(self.bottom_left_container, bg="#1E1E1E")
        self.timeline_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.lbl_article_details = tk.Label(self.timeline_frame, text="Sélectionnez un article pour voir son parcours", font=("Arial", 16, "bold"), bg="#1E1E1E", fg="#4da6ff", wraplength=500, justify="center")
        self.lbl_article_details.pack(pady=5)
        
        self.frise_frame = tk.Frame(self.timeline_frame, bg="#1E1E1E")
        self.frise_frame.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        self.timeline_blocks = {}
        postes_list = get_postes_disponibles()
        for i, poste in enumerate(postes_list):
            poste_nom = poste.split("-")[-1].strip()
            block = tk.Frame(self.frise_frame, bg="#2D2D30", relief=tk.RAISED, borderwidth=2)
            self.frise_frame.columnconfigure(i, weight=1)
            block.grid(row=0, column=i, sticky="nsew", padx=2, pady=5)
            
            lbl_nom = tk.Label(block, text=poste_nom, font=("Arial", 11, "bold"), bg="#2D2D30", fg="white", wraplength=100)
            lbl_nom.pack(pady=(10, 0))
            
            lbl_count = tk.Label(block, text="0 / 0", font=("Arial", 22, "bold"), bg="#2D2D30", fg="white")
            lbl_count.pack(expand=True, pady=5)
            
            self.timeline_blocks[poste] = {'frame': block, 'lbl_nom': lbl_nom, 'lbl_count': lbl_count}
            
        # --- FRAME 2 : Focus Flash Scan (Caché par défaut) ---
        self.scan_flash_frame = tk.Frame(self.bottom_left_container, bg="#1E1E1E")
        
        self.scan_flash_frame.columnconfigure(0, weight=1)
        self.scan_flash_frame.columnconfigure(1, weight=1)
        
        dim_info = tk.Frame(self.scan_flash_frame, bg="#1E1E1E")
        dim_info.grid(row=0, column=0, sticky="nsew", padx=10)
        
        self.lbl_designation = tk.Label(dim_info, text="Désignation : --", font=("Arial", 16), bg="#1E1E1E", fg="white", wraplength=300, justify="left")
        self.lbl_designation.pack(pady=10)
        
        self.dim_frame = tk.Frame(dim_info, bg="#1E1E1E", highlightbackground="#4da6ff", highlightthickness=2)
        self.dim_frame.pack(fill=tk.X, pady=5)
        self.lbl_dim = tk.Label(self.dim_frame, text="DIMENSIONS\n-- x --", font=("Arial", 22, "bold"), bg="#1E1E1E", fg="#4da6ff")
        self.lbl_dim.pack(pady=10)

        prog_info = tk.Frame(self.scan_flash_frame, bg="#1E1E1E")
        prog_info.grid(row=0, column=1, sticky="nsew", padx=10)
        
        self.lbl_progression_title = tk.Label(prog_info, text="PROGRESSION", font=("Arial", 14), bg="#1E1E1E", fg="#AAAAAA")
        self.lbl_progression_title.pack(pady=(10, 0))
        
        self.lbl_progression = tk.Label(prog_info, text="0 / 0", font=("Arial", 70, "bold"), bg="#1E1E1E", fg="white")
        self.lbl_progression.pack(expand=True)
        
        # 3. Footer (Bandeau inférieur)
        self.footer_frame = tk.Frame(self.tab_atelier, bg="#333333", height=120)
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer_frame.pack_propagate(False)
        
        self.lbl_scan_status = tk.Label(self.footer_frame, text="En attente de scan...", 
                                        font=("Arial", 22, "bold"), fg="white", bg="#333333")
        self.lbl_scan_status.pack(pady=(15, 10))
        
        self.scan_var = tk.StringVar()
        self.scan_entry = tk.Entry(self.footer_frame, textvariable=self.scan_var, font=("Arial", 18), justify="center", width=30)
        self.scan_entry.pack(pady=5)
        self.scan_entry.bind("<Return>", self.on_scan)
        
        self.status_frame = self.footer_frame
        
        # Construction de l'interface Bureau d'Étude
        self.build_be_ui()
        
    def build_be_ui(self):
        # Header BE
        header_be = tk.Frame(self.tab_be, bg="#2C3E50", height=80)
        header_be.pack(fill=tk.X, side=tk.TOP)
        header_be.pack_propagate(False)
        self.lbl_be_header = tk.Label(header_be, text="📐 BUREAU D'ÉTUDE", font=("Arial", 20, "bold"), fg="white", bg="#2C3E50")
        self.lbl_be_header.pack(side=tk.LEFT, padx=20, pady=20)
        
        # Style pour le notebook BE
        style = ttk.Style()
        style.configure("BENotebook.TNotebook", background="#1E1E1E")
        style.configure("BENotebook.TNotebook.Tab", padding=[15, 5], font=('Arial', 11, 'bold'))
        
        # Notebook BE
        self.be_notebook = ttk.Notebook(self.tab_be, style="BENotebook.TNotebook")
        self.be_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.tab_be_gen = tk.Frame(self.be_notebook, bg="#1E1E1E")
        self.tab_be_matrice = tk.Frame(self.be_notebook, bg="#1E1E1E")
        self.tab_be_charge = tk.Frame(self.be_notebook, bg="#1E1E1E")
        
        self.be_notebook.add(self.tab_be_gen, text="📝 Génération OF")
        self.be_notebook.add(self.tab_be_matrice, text="📊 Matrice Commandes")
        self.be_notebook.add(self.tab_be_charge, text="🏭 Charge Machines")
        
        self.be_notebook.bind("<<NotebookTabChanged>>", self.on_be_tab_changed)
        
        self.build_be_gen_ui()
        self.build_be_matrice_ui()
        self.build_be_charge_ui()

    def on_main_tab_changed(self, event):
        tab_id = self.notebook.select()
        tab_text = self.notebook.tab(tab_id, "text")
        if "BUREAU" in tab_text:
            if hasattr(self, "be_notebook"):
                be_tab_id = self.be_notebook.select()
                if be_tab_id:
                    be_tab_text = self.be_notebook.tab(be_tab_id, "text")
                    if "Matrice" in be_tab_text:
                        self.refresh_be_matrice()
                    elif "Charge" in be_tab_text:
                        self.refresh_be_charge()

    def on_be_tab_changed(self, event):
        tab_id = self.be_notebook.select()
        tab_text = self.be_notebook.tab(tab_id, "text")
        self.lbl_be_header.config(text=f"📐 BUREAU D'ÉTUDE - {tab_text}")
        
        if "Matrice" in tab_text:
            self.refresh_be_matrice()
        elif "Charge" in tab_text:
            self.refresh_be_charge()

    def build_be_gen_ui(self):
        # Body BE Gen
        body_be = tk.Frame(self.tab_be_gen, bg="#1E1E1E")
        body_be.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        body_be.columnconfigure(0, weight=3) # Commandes (30%)
        body_be.columnconfigure(1, weight=7) # Détails (70%)
        body_be.rowconfigure(0, weight=1)
        
        # --- Gauche : Commandes ---
        left_be = tk.Frame(body_be, bg="#2D2D30")
        left_be.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(left_be, text="COMMANDES SAGE", font=("Segoe UI", 12, "bold"), fg="#4da6ff", bg="#2D2D30").pack(pady=10)
        
        cols_be_cmd = ("cmd", "client")
        tree_be_cmd_frame = tk.Frame(left_be)
        tree_be_cmd_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        scroll_be_cmd = ttk.Scrollbar(tree_be_cmd_frame, orient="vertical")
        
        self.tree_be_cmd = ttk.Treeview(tree_be_cmd_frame, columns=cols_be_cmd, show="headings", selectmode="browse", yscrollcommand=scroll_be_cmd.set)
        scroll_be_cmd.config(command=self.tree_be_cmd.yview)
        
        self.tree_be_cmd.heading("cmd", text="Commande")
        self.tree_be_cmd.heading("client", text="Client")
        self.tree_be_cmd.column("cmd", width=100)
        self.tree_be_cmd.column("client", width=150)
        
        scroll_be_cmd.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_be_cmd.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.tree_be_cmd.tag_configure('terminee', background='#2e5e32')
        self.tree_be_cmd.tag_configure('encours', background='#825018')
        self.tree_be_cmd.tag_configure('pas_demarre', background='#424242', foreground='#AAAAAA')
        
        self.tree_be_cmd.tag_configure('terminee_sel', background='#1E7B35', foreground='white', font=("Segoe UI", 10, "bold underline"))
        self.tree_be_cmd.tag_configure('encours_sel', background='#A85C1C', foreground='white', font=("Segoe UI", 10, "bold underline"))
        self.tree_be_cmd.tag_configure('pas_demarre_sel', background='#005A9E', foreground='white', font=("Segoe UI", 10, "bold underline"))
        self.tree_be_cmd.tag_configure('default_sel', background='#005A9E', foreground='white', font=("Segoe UI", 10, "bold underline"))
        self.tree_be_cmd.bind("<<TreeviewSelect>>", lambda e: [self._update_selection_tags(self.tree_be_cmd), self.on_be_order_select(e)])
        
        font_sel = ("Segoe UI", 11, "bold underline")
        sel_blue = '#005A9E'
        
        # --- Droite : Détails ---
        right_be = tk.Frame(body_be, bg="#2D2D30")
        right_be.grid(row=0, column=1, sticky="nsew")
        
        # Haut: Lignes Sage
        tk.Label(right_be, text="LIGNES COMMERCIALES (SAGE)", font=("Segoe UI", 12, "bold"), fg="#CCCCCC", bg="#2D2D30").pack(pady=(10,0))
        
        cols_be_sage = ("ligne", "ref", "designation", "dim", "qte")
        tree_be_sage_frame = tk.Frame(right_be)
        tree_be_sage_frame.pack(fill=tk.X, padx=10, pady=5)
        
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
        tk.Label(right_be, text="SOUS-ENSEMBLES DE FABRICATION (Nomenclature de l'Atelier)", font=("Segoe UI", 12, "bold"), fg="#4CAF50", bg="#2D2D30").pack(pady=(20,0))
        
        # Actions BE
        action_frame = tk.Frame(right_be, bg="#2D2D30")
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        btn_add_of = tk.Button(action_frame, text="➕ Ajouter un Produit (OF)", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=self.add_of_dialog)
        btn_add_of.pack(side=tk.LEFT, padx=5)
        btn_print = tk.Button(action_frame, text="🖨️ Imprimer Étiquettes", bg="#FF9800", fg="white", font=("Arial", 10, "bold"))
        btn_print.pack(side=tk.LEFT, padx=5)
        
        cols_be_of = ("id", "prod", "design", "observ", "qte", "parcours")
        tree_be_of_frame = tk.Frame(right_be)
        tree_be_of_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=(5, 10))
        
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
                
            self.lbl_title.config(text=f"TABLEAU DE BORD | POSTE : {self.poste_nom_court.upper()}")
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
                    ligne_data = lignes_dict.get(l_key)
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
        header_mat = tk.Frame(self.tab_be_matrice, bg="#2C3E50", height=80)
        header_mat.pack(fill=tk.X, side=tk.TOP)
        header_mat.pack_propagate(False)
        tk.Label(header_mat, text="📊 BUREAU D'ÉTUDE - MATRICE COMMANDES", font=("Arial", 20, "bold"), fg="white", bg="#2C3E50").pack(side=tk.LEFT, padx=20, pady=20)
        
        btn_refresh = tk.Button(header_mat, text="🔄 Actualiser", font=("Arial", 12, "bold"), bg="#4da6ff", fg="white", command=self.refresh_be_matrice)
        btn_refresh.pack(side=tk.RIGHT, padx=20, pady=20)
        
        body_mat = tk.Frame(self.tab_be_matrice, bg="#1E1E1E")
        body_mat.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        scroll_y = ttk.Scrollbar(body_mat, orient="vertical")
        scroll_x = ttk.Scrollbar(body_mat, orient="horizontal")
        
        self.tree_matrice = ttk.Treeview(body_mat, xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set, show="tree headings")
        scroll_y.config(command=self.tree_matrice.yview)
        scroll_x.config(command=self.tree_matrice.xview)
        
        self.tree_matrice.heading("#0", text="Désignation (Hiérarchie)")
        self.tree_matrice.column("#0", width=400, anchor="w")
        
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree_matrice.pack(expand=True, fill=tk.BOTH)
        
        # Tags for 3 states
        self.tree_matrice.tag_configure("pas_demarre", background="#424242", foreground="#AAAAAA")
        self.tree_matrice.tag_configure("encours", background="#F57C00", foreground="white")
        self.tree_matrice.tag_configure("terminee", background="#388E3C", foreground="white")
        
        sel_blue = '#005A9E'
        font_sel = ("Segoe UI", 11, "bold underline")
        self.tree_matrice.tag_configure("pas_demarre_sel", background=sel_blue, foreground="white", font=font_sel)
        self.tree_matrice.tag_configure("encours_sel", background=sel_blue, foreground="white", font=font_sel)
        self.tree_matrice.tag_configure("terminee_sel", background=sel_blue, foreground="white", font=font_sel)
        
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
        header_charge = tk.Frame(self.tab_be_charge, bg="#2C3E50", height=80)
        header_charge.pack(fill=tk.X, side=tk.TOP)
        header_charge.pack_propagate(False)
        tk.Label(header_charge, text="🏭 BUREAU D'ÉTUDE - CHARGE MACHINES", font=("Arial", 20, "bold"), fg="white", bg="#2C3E50").pack(side=tk.LEFT, padx=20, pady=20)
        
        btn_refresh = tk.Button(header_charge, text="🔄 Actualiser", font=("Arial", 12, "bold"), bg="#4da6ff", fg="white", command=self.refresh_be_charge)
        btn_refresh.pack(side=tk.RIGHT, padx=20, pady=20)
        
        body = tk.Frame(self.tab_be_charge, bg="#1E1E1E")
        body.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        left_frame = tk.Frame(body, bg="#2D2D30", width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="SÉLECTION MACHINE", font=("Segoe UI", 12, "bold"), fg="#4da6ff", bg="#2D2D30").pack(pady=10)
        
        self.tree_machines = ttk.Treeview(left_frame, columns=("machine",), show="headings")
        self.tree_machines.heading("machine", text="Poste / Machine")
        self.tree_machines.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        self.tree_machines.bind("<<TreeviewSelect>>", self.on_machine_select)
        
        self.tree_machines.tag_configure('default_sel', background='#005A9E', foreground='white', font=("Segoe UI", 11, "bold underline"))
        
        right_frame = tk.Frame(body, bg="#1E1E1E")
        right_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        right_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(1, weight=1)
        right_frame.columnconfigure(2, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        tk.Label(right_frame, text="📥 PAS ENCORE DÉMARRÉ (A Faire)", bg="#424242", fg="white", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        tk.Label(right_frame, text="⏳ EN COURS (Scans démarrés)", bg="#F57C00", fg="white", font=("Arial", 12, "bold")).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        tk.Label(right_frame, text="✅ TERMINÉ", bg="#388E3C", fg="white", font=("Arial", 12, "bold")).grid(row=0, column=2, sticky="ew", padx=5, pady=5)
        
        self.list_attente = tk.Listbox(right_frame, bg="#2D2D30", fg="white", font=("Arial", 10))
        self.list_encours = tk.Listbox(right_frame, bg="#2D2D30", fg="white", font=("Arial", 10))
        self.list_termine = tk.Listbox(right_frame, bg="#2D2D30", fg="white", font=("Arial", 10))
        
        self.list_attente.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.list_encours.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.list_termine.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)

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
                    ligne_data = lignes_dict.get(l_key)
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
        self.lbl_commande.config(text=f"Commande : {do_piece}")
        self.lbl_client.config(text=f"Client : {client}")
        
        self.lbl_lignes_title.config(text=f"ARTICLES DE LA COMMANDE : {do_piece}")
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
            self.lbl_article_details.config(text="Aucun article à produire pour ce poste sur cette commande.")
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
        
        self.lbl_article_details.config(text=f"OF: {key} - {prod} - {design}\\nDimensions : {dim} | Qté: {qte}")
        
        # Reconstruire dynamiquement la timeline pour CET OF
        for widget in self.timeline_frame.winfo_children():
            if widget != self.timeline_frame.winfo_children()[0]: # Keep the title
                widget.destroy()
                
        self.timeline_blocks = {}
        timeline_container = tk.Frame(self.timeline_frame, bg="#2D2D30")
        timeline_container.pack(expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        cursor.execute("SELECT CodeOp FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (key,))
        routing = cursor.fetchall()
        
        for (op,) in routing:
            block = tk.Frame(timeline_container, bg="#1E1E1E", bd=1, relief=tk.SOLID)
            block.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            
            # Fetch operation name
            cursor.execute("SELECT LibelOp FROM Operations WHERE RefOp = ?", (op,))
            op_row = cursor.fetchone()
            op_name = op_row[0] if op_row else f"{op} (Non défini)"
            lbl_nom = tk.Label(block, text=op_name, font=("Arial", 9, "bold"), fg="white", bg="#1E1E1E", wraplength=80)
            lbl_nom.pack(pady=(10,5))
            
            # Count total scans for this operation for this OF
            cursor.execute('''
                SELECT COUNT(*) FROM Scans 
                JOIN Postes ON Scans.Poste = Postes.CodPost 
                WHERE Scans.ID_OF = ? AND Postes.RefOp = ?
            ''', (key, op))
            count = cursor.fetchone()[0]
            
            lbl_count = tk.Label(block, text=f"{count} / {qte}", font=("Arial", 14, "bold"), fg="#CCCCCC", bg="#1E1E1E")
            lbl_count.pack(expand=True, pady=5)
            
            # Highlight if it's our current operation
            mon_op = self.get_mon_op()
            if op == mon_op:
                block.config(bg="#004d40", highlightbackground="#00bfa5", highlightthickness=2)
                lbl_nom.config(bg="#004d40")
                lbl_count.config(bg="#004d40", fg="white")
                if count >= qte:
                    lbl_count.config(fg="#81c784") # Green if done
                
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
        
        sim_win = tk.Toplevel(self.root)
        sim_win.title("Simulateur de Scan")
        sim_win.geometry("450x320")
        sim_win.config(bg="#1E1E1E")
        
        tk.Label(sim_win, text="SIMULATEUR DE DOUCHETTE", font=("Arial", 14, "bold"), bg="#1E1E1E", fg="#FF9800").pack(pady=10)
        
        info_frame = tk.Frame(sim_win, bg="#2D2D30", padx=10, pady=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(info_frame, text=f"Désignation: {designation}", font=("Arial", 12), bg="#2D2D30", fg="white", wraplength=350, justify="left").pack(anchor="w", pady=2)
        tk.Label(info_frame, text=f"Réf: {prod}", font=("Arial", 12), bg="#2D2D30", fg="#CCCCCC").pack(anchor="w", pady=2)
        tk.Label(info_frame, text=f"Dim: {dim}", font=("Arial", 12), bg="#2D2D30", fg="#CCCCCC").pack(anchor="w", pady=2)
        
        tk.Label(info_frame, text=f"Code-Barres : {barcode}", font=("Arial", 14, "bold"), bg="#2D2D30", fg="#4da6ff").pack(pady=15)
        
        def do_scan():
            self.process_scan(barcode)
            sim_win.destroy()
            
        tk.Button(sim_win, text="Scanner / Valider", font=("Arial", 14, "bold"), bg="#4CAF50", fg="white", command=do_scan).pack(pady=15, fill=tk.X, padx=20)

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
            self.lbl_commande.config(text=f"Commande : {do_piece}")
            self.lbl_client.config(text=f"Client : {client}")
            self.lbl_designation.config(text="Désignation : --")
            self.lbl_dim.config(text="DIMENSIONS\n-- x --")
            self.lbl_progression.config(text="0 / 0")
            
            # Sélection dans l'arbre pour charger les articles
            if self.tree_cmd.exists(do_piece):
                self.tree_cmd.selection_set(do_piece)
                self.tree_cmd.see(do_piece)
                self.on_order_select(None)
            else:
                self.lbl_lignes_title.config(text=f"ARTICLES DE LA COMMANDE : {do_piece}")
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
                    self.lbl_article_details.config(text="Aucun article à produire pour ce poste sur cette commande.")
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
            self.lbl_commande.config(text=f"Commande : {do_piece}")
            self.lbl_client.config(text=f"Client : {client}")
            self.lbl_designation.config(text=f"Désignation : {designation}")
            dim_text = observ if observ else "--"
            self.lbl_dim.config(text=f"OF : {key}\\nDimensions : {dim_text}")
            self.lbl_progression.config(text=f"{nouveau_count} / {qte_totale}")
            
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
        root = tk.Tk()
        app = SotraglaceApp(root)
        root.mainloop()
    except Exception as e:
        with open("crash.log", "w") as f:
            f.write(traceback.format_exc())


