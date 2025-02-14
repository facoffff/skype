from flask import Flask, render_template, request, redirect, url_for, flash, session
from skpy import Skype
import os
import json
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'una_chiave_segretissima'
# Sessione permanente per 365 giorni
app.permanent_session_lifetime = timedelta(days=365)

DATA_FILE = "groups.json"

def load_groups():
    """Carica i gruppi dal file JSON, se esiste, altrimenti restituisce un dizionario vuoto."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
            return data
    else:
        return {}

def save_groups():
    """Salva il dizionario dei gruppi nel file JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(groups, f, indent=4)

# Carica i gruppi al momento dell'avvio dell'applicazione
groups = load_groups()

# ---------------------------
# Route per "/" (root)
# ---------------------------
@app.route('/')
def index():
    # Reindirizza l'utente alla pagina di login
    return redirect(url_for('login'))

# ---------------------------
# 1. Login
# ---------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            # Verifica delle credenziali Skype (a scopo dimostrativo)
            skype = Skype(username, password)
            session.permanent = True
            session['username'] = username
            session['password'] = password
            session['logged_in'] = True
            flash("Login effettuato con successo.", "success")
            return redirect(url_for('main'))
        except Exception as e:
            flash(f"Errore durante l'accesso: {e}", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logout effettuato.", "success")
    return redirect(url_for('login'))

# ---------------------------
# 2. Main / Invio Messaggi
# ---------------------------
@app.route('/main', methods=['GET', 'POST'])
def main():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Recupera i gruppi selezionati (checkbox con name="groups[]")
        selected_groups = request.form.getlist('groups[]')
        messaggio = request.form.get('messaggio')
        
        if not selected_groups:
            flash("Seleziona almeno un gruppo.", "error")
            return redirect(url_for('main'))
        if not messaggio:
            flash("Inserisci un messaggio.", "error")
            return redirect(url_for('main'))
        
        username = session.get('username')
        password = session.get('password')
        try:
            skype = Skype(username, password)
        except Exception as e:
            flash(f"Errore durante l'accesso a Skype: {e}", "error")
            return redirect(url_for('login'))
        
        # Raccoglie tutti i contatti selezionati eliminando i duplicati
        unique_contacts = {}
        for group in selected_groups:
            selected_contacts = request.form.getlist(f'contacts[{group}][]')
            if not selected_contacts:
                flash(f"Nessun contatto selezionato nel gruppo '{group}'.", "error")
                continue
            for contact in groups.get(group, []):
                if contact['skype_name'] in selected_contacts:
                    unique_contacts[contact['skype_name']] = contact['alias']
        
        # Invia il messaggio una sola volta per ogni contatto unico
        for skype_name, alias in unique_contacts.items():
            try:
                chat = skype.contacts[skype_name].chat
                chat.sendMsg(messaggio)
                flash(f"Messaggio inviato a {alias} ({skype_name}).", "success")
            except Exception as e:
                flash(f"Errore inviando messaggio a {alias} ({skype_name}): {e}", "error")
        
        return redirect(url_for('main'))
    
    return render_template('main.html', groups=groups)

# ---------------------------
# 3. Rubrica
# ---------------------------
@app.route('/rubrica')
def rubrica():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('rubrica.html', groups=groups)

@app.route('/rubrica/new_group', methods=['POST'])
def new_group():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    group_name = request.form.get('group_name')
    if not group_name:
        flash("Inserisci un nome per il gruppo.", "error")
        return redirect(url_for('rubrica'))
    if group_name in groups:
        flash("Il gruppo esiste già.", "error")
        return redirect(url_for('rubrica'))
    groups[group_name] = []
    save_groups()
    flash(f"Gruppo '{group_name}' creato con successo.", "success")
    return redirect(url_for('rubrica'))

@app.route('/rubrica/delete_group/<group_name>', methods=['POST'])
def delete_group(group_name):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if group_name in groups:
        del groups[group_name]
        save_groups()
        flash(f"Gruppo '{group_name}' eliminato.", "success")
    else:
        flash("Gruppo non trovato.", "error")
    return redirect(url_for('rubrica'))

@app.route('/rubrica/add_contact/<group_name>', methods=['POST'])
def add_contact(group_name):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    skype_name = request.form.get('skype_name')
    alias = request.form.get('alias')
    if not skype_name or not alias:
        flash("Compila entrambi i campi per aggiungere un contatto.", "error")
        return redirect(url_for('rubrica'))
    if group_name not in groups:
        flash("Gruppo non trovato.", "error")
        return redirect(url_for('rubrica'))
    groups[group_name].append({'skype_name': skype_name.strip(), 'alias': alias.strip()})
    save_groups()
    flash(f"Contatto '{alias}' aggiunto al gruppo '{group_name}'.", "success")
    return redirect(url_for('rubrica'))

@app.route('/rubrica/delete_contact/<group_name>/<int:contact_index>', methods=['POST'])
def delete_contact(group_name, contact_index):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if group_name in groups and 0 <= contact_index < len(groups[group_name]):
        removed = groups[group_name].pop(contact_index)
        save_groups()
        flash(f"Contatto '{removed['alias']}' eliminato dal gruppo '{group_name}'.", "success")
    else:
        flash("Contatto non trovato.", "error")
    return redirect(url_for('rubrica'))

@app.route('/rubrica/edit_contact/<group_name>/<int:contact_index>', methods=['GET', 'POST'])
def edit_contact(group_name, contact_index):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if group_name not in groups or contact_index < 0 or contact_index >= len(groups[group_name]):
        flash("Contatto non trovato.", "error")
        return redirect(url_for('rubrica'))
    
    contact = groups[group_name][contact_index]
    
    if request.method == 'POST':
        skype_name = request.form.get('skype_name')
        alias = request.form.get('alias')
        if not skype_name or not alias:
            flash("Compila entrambi i campi.", "error")
            return redirect(url_for('edit_contact', group_name=group_name, contact_index=contact_index))
        groups[group_name][contact_index] = {'skype_name': skype_name.strip(), 'alias': alias.strip()}
        save_groups()
        flash("Contatto aggiornato.", "success")
        return redirect(url_for('rubrica'))
    
    return render_template('edit_contact.html', group_name=group_name, contact_index=contact_index, contact=contact)

if __name__ == '__main__':
    app.run(debug=True)
