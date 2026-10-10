import re

def patch():
    with open('suivi_atelier.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update AddOfDialog UI and Logic
    old_gamme_preview = """        # Gamme Preview
        tk.Label(form_frame, text="Gamme standard prévue :", font=("Arial", 12, "bold"), bg="#2D2D30", fg="#4da6ff").grid(row=4, column=0, columnspan=2, sticky="w", pady=(15,5))
        self.lbl_gamme = tk.Label(form_frame, text="Sélectionnez un produit...", font=("Arial", 11, "italic"), bg="#2D2D30", fg="#CCCCCC", justify="left")
        self.lbl_gamme.grid(row=5, column=0, columnspan=2, sticky="w", pady=0)"""
        
    new_gamme_preview = """        # Gamme Preview avec choix des postes
        tk.Label(form_frame, text="Gamme & Assignation des Postes :", font=("Arial", 12, "bold"), bg="#2D2D30", fg="#4da6ff").grid(row=4, column=0, columnspan=2, sticky="w", pady=(15,5))
        
        self.gamme_frame = tk.Frame(form_frame, bg="#1E1E1E", bd=1, relief="sunken")
        self.gamme_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=5)
        self.gamme_vars = []"""
    
    content = content.replace(old_gamme_preview, new_gamme_preview)
    
    old_on_prod_select = """            # Afficher la gamme
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT Operations.LibelOp FROM Gammes JOIN Operations ON Gammes.CodeOp = Operations.RefOp WHERE RefProd = ? ORDER BY Ordre", (ref,))
            gammes = cursor.fetchall()
            if gammes:
                texte_gamme = " ➔ ".join([g[0] for g in gammes])
                self.lbl_gamme.config(text=texte_gamme)
            else:
                self.lbl_gamme.config(text="Aucune gamme définie pour ce produit.")"""
                
    new_on_prod_select = """            # Construire la gamme interactive
            for widget in self.gamme_frame.winfo_children():
                widget.destroy()
            self.gamme_vars = []
            
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT Gammes.Ordre, Gammes.CodeOp, Operations.LibelOp FROM Gammes JOIN Operations ON Gammes.CodeOp = Operations.RefOp WHERE RefProd = ? ORDER BY Ordre", (ref,))
            gammes = cursor.fetchall()
            
            if not gammes:
                tk.Label(self.gamme_frame, text="Aucune gamme définie pour ce produit.", bg="#1E1E1E", fg="white").pack(pady=10)
                return
                
            for step in gammes:
                ordre, code_op, libel_op = step
                
                row_frame = tk.Frame(self.gamme_frame, bg="#1E1E1E")
                row_frame.pack(fill=tk.X, padx=10, pady=2)
                
                tk.Label(row_frame, text=f"{ordre}. {libel_op}", font=("Arial", 10, "bold"), bg="#1E1E1E", fg="white", width=20, anchor="w").pack(side=tk.LEFT)
                
                # Chercher les postes compatibles
                cursor.execute("SELECT CodPost, DesPost FROM Postes WHERE RefOp = ?", (code_op,))
                postes_compatibles = ["Libre (N'importe lequel)"] + [f"{r[0]} - {r[1]}" for r in cursor.fetchall()]
                
                var = tk.StringVar(value=postes_compatibles[0])
                cb = ttk.Combobox(row_frame, textvariable=var, values=postes_compatibles, state="readonly", width=30)
                cb.pack(side=tk.LEFT, padx=10)
                
                self.gamme_vars.append({'ordre': ordre, 'code_op': code_op, 'var': var})"""
    
    content = content.replace(old_on_prod_select, new_on_prod_select)
    
    old_save_insert_gamme = """        # Insérer la gamme
        cursor.execute("SELECT CodeOp, Ordre FROM Gammes WHERE RefProd = ? ORDER BY Ordre", (ref_prod,))
        for step in cursor.fetchall():
            cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp) VALUES (?, ?, ?)", (new_id, step[1], step[0]))"""
            
    new_save_insert_gamme = """        # Insérer la gamme avec postes assignés
        for step in self.gamme_vars:
            val = step['var'].get()
            poste_assigne = val.split(" - ")[0] if val != "Libre (N'importe lequel)" else None
            cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", (new_id, step['ordre'], step['code_op'], poste_assigne))"""
            
    content = content.replace(old_save_insert_gamme, new_save_insert_gamme)
    
    # 2. Update Dynamic Kanban to respect Poste_Assigne
    # Inside update_lines_view
    update_lines_regex = r"            for i, step in enumerate\(routing\):\s+if step\[0\] == mon_op:\s+my_index = i\s+break"
    new_update_lines = """            codpost = self.poste_actuel.split(" - ")[0]
            for i, step in enumerate(routing):
                if step[0] == mon_op:
                    # step[1] is Poste_Assigne
                    if step[1] is None or step[1] == codpost:
                        my_index = i
                        break"""
    content = re.sub(update_lines_regex, new_update_lines, content)
    
    # Inside get_order_progress
    get_progress_old = """        # Get all OFs for this order that have 'mon_op' in their routing
        cursor.execute('''
            SELECT C.ID_OF, C.Qte FROM CdeDetail C
            JOIN OF_Gammes G ON C.ID_OF = G.ID_OF
            WHERE C.CDE = ? AND G.CodeOp = ?
        ''', (do_piece, mon_op))"""
    
    get_progress_new = """        # Get all OFs for this order that have 'mon_op' in their routing AND are assigned to me or free
        codpost = self.poste_actuel.split(" - ")[0]
        cursor.execute('''
            SELECT C.ID_OF, C.Qte FROM CdeDetail C
            JOIN OF_Gammes G ON C.ID_OF = G.ID_OF
            WHERE C.CDE = ? AND G.CodeOp = ? AND (G.Poste_Assigne IS NULL OR G.Poste_Assigne = ?)
        ''', (do_piece, mon_op, codpost))"""
        
    content = content.replace(get_progress_old, get_progress_new)

    with open('suivi_atelier.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Patch applied successfully!")

if __name__ == '__main__':
    patch()
