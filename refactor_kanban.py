import re
import sys

def patch():
    with open('suivi_atelier.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add get_mon_op
    get_mon_op_code = """
    def get_mon_op(self):
        cursor = self.db_conn.cursor()
        codpost = self.poste_actuel.split(" - ")[0]
        cursor.execute("SELECT RefOp FROM Postes WHERE CodPost = ?", (codpost,))
        row = cursor.fetchone()
        return row[0] if row else None
"""
    # Insert after load_config
    content = content.replace("def load_scans_cache(self):", get_mon_op_code + "\n    def load_scans_cache(self):")

    # 2. Rewrite update_lines_view
    update_lines_code = """
    def update_lines_view(self, do_piece):
        for item in self.tree_lignes.get_children():
            self.tree_lignes.delete(item)
            
        mon_op = self.get_mon_op()
        if not mon_op: return
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT ID_OF, PROD, DESIGN, OBSERV, Qte FROM CdeDetail WHERE CDE = ?", (do_piece,))
        ofs = cursor.fetchall()
        
        for of in ofs:
            id_of, prod, design, observ, qte = of
            
            # Fetch routing
            cursor.execute("SELECT CodeOp, Poste_Assigne FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (id_of,))
            routing = cursor.fetchall()
            
            # Find my position in routing
            my_index = -1
            for i, step in enumerate(routing):
                if step[0] == mon_op:
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
            
            if mes_scans >= qte:
                statut_txt = "Terminé"
                situation = "✔ Terminé à ce poste"
                tag = "terminee"
            elif dispo > 0:
                statut_txt = f"En cours ({mes_scans}/{qte})"
                situation = f"► Prêt à produire : {dispo} dispo"
                tag = "pret"
            elif mes_scans > 0:
                statut_txt = f"En cours ({mes_scans}/{qte})"
                situation = f"En attente étape précédente"
                tag = "encours"
            else:
                situation = "Bloqué (Étape précédente non finie)"
                tag = "attente"
                
            dim = observ if observ else "--"
            self.tree_lignes.insert("", "end", iid=id_of, values=("OF", prod, design, dim, qte, statut_txt, situation), tags=(tag,))
"""
    # Replace the old update_lines_view completely using regex
    content = re.sub(r'    def update_lines_view\(self, do_piece\):.*?        # Focus Industriel', update_lines_code + '\n        # Focus Industriel', content, flags=re.DOTALL)

    # 3. Fix Timeline to be dynamic when OF is selected
    on_article_select_code = """
    def on_article_select(self, event=None, force_show=True):
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
        
        self.lbl_article_details.config(text=f"OF: {key} - {prod} - {design}\\nObs: {dim} | Qté: {qte}")
        
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
            op_name = cursor.fetchone()[0]
            
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
"""
    content = re.sub(r'    def on_article_select\(self, event=None, force_show=True\):.*?    def on_scan', on_article_select_code + '\n    def on_scan', content, flags=re.DOTALL)

    # 4. Modify get_order_progress to look at OFs instead of Sage Lines
    get_order_progress_code = """
    def get_order_progress(self, do_piece):
        cursor = self.db_conn.cursor()
        mon_op = self.get_mon_op()
        if not mon_op: return 0, 0, "N/A"
        
        # Get all OFs for this order that have 'mon_op' in their routing
        cursor.execute('''
            SELECT C.ID_OF, C.Qte FROM CdeDetail C
            JOIN OF_Gammes G ON C.ID_OF = G.ID_OF
            WHERE C.CDE = ? AND G.CodeOp = ?
        ''', (do_piece, mon_op))
        
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
"""
    content = re.sub(r'    def get_order_progress\(self, do_piece\):.*?    def build_ui', get_order_progress_code + '\n    def build_ui', content, flags=re.DOTALL)

    # 5. Fix on_scan to use ID_OF
    on_scan_patch = """
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
        cursor.execute("SELECT CDE, PROD, DESIGN, Qte FROM CdeDetail WHERE ID_OF = ?", (key,))
        of_data = cursor.fetchone()
        
        if not of_data:
            self.update_status_bar("error", f"ERREUR : Code-barres inconnu ({qr_code})")
            return
            
        do_piece, prod, designation, qte_totale = of_data
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
            scanned, total, pct_str = self.get_order_progress(do_piece)
            if self.tree_cmd.exists(do_piece):
                tag = "encours" if scanned < total else "terminee"
                row_vals = self.tree_cmd.item(do_piece, 'values')
                if len(row_vals) >= 4:
                    self.tree_cmd.item(do_piece, values=(row_vals[0], row_vals[1], row_vals[2], f"{scanned}/{total} ({pct_str})"), tags=(tag,))
            
            # Mettre à jour les infos du flash
            self.lbl_commande.config(text=f"Commande : {do_piece}")
            self.lbl_client.config(text=f"Client : {client}")
            self.lbl_designation.config(text=f"Désignation : {designation}")
            self.lbl_dim.config(text=f"OF\\n{key}")
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
"""
    content = re.sub(r'        # LOGIQUE D\'ARTICLE \(ART-\.\.\.\).*?        if qr_code\.startswith\("ART-"\):.*?            else:\n                self.update_status_bar\("progress", f"OK : Pièce enregistrée \({designation}\)"\)', on_scan_patch, content, flags=re.DOTALL)

    with open('suivi_atelier.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch()
