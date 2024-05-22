import pandas as pd
import pulp as pl
from flask import Flask, render_template, request
from flask_mysqldb import MySQL

app = Flask(__name__)

# Configuration de la base de données MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'maintenance_db'

mysql = MySQL(app)


def optimize_maintenance(df, optimization_type, max_maintenance_duration):
    # Conversion des colonnes en float
    for col in ['maintenance_cost', 'maintenance_duration', 'downtime_hours', 'downtime_cost', 'production_quality', 'production_hours', 'production_cost', 'availability', 'lifetime']:
        df[col] = df[col].astype(float)

    # Créer un problème de programmation linéaire
    prob = pl.LpProblem("MaintenanceOptimization", pl.LpMaximize if optimization_type != "minimize_cost" else pl.LpMinimize)
    x = pl.LpVariable.dicts("maintenance", df.index, lowBound=0, cat='Continuous')

    # Fonction objectif
    if optimization_type == "minimize_cost":
        prob += pl.lpSum([df.loc[i, 'maintenance_cost'] * x[i] for i in df.index])
    elif optimization_type == "maximize_quality":
        prob += pl.lpSum([df.loc[i, 'production_quality'] * x[i] for i in df.index])
    elif optimization_type == "maximize_availability":
        prob += pl.lpSum([df.loc[i, 'availability'] * x[i] for i in df.index])
    elif optimization_type == "maximize_lifetime":
        prob += pl.lpSum([df.loc[i, 'lifetime'] * x[i] for i in df.index])

    # Contraintes
    prob += pl.lpSum([df.loc[i, 'maintenance_duration'] * x[i] for i in df.index]) <= max_maintenance_duration

    # Ajout d'une contrainte de maintenance minimale pour chaque machine
    for i in df.index:
        prob += x[i] >= 0.1  # par exemple, assurer au moins 10% de maintenance

    # Résoudre le problème
    prob.solve()

    # Statut de la solution
    print("Statut de la solution:", pl.LpStatus[prob.status])

    optimized_maintenance = []
    for i in df.index:
        optimized_maintenance.append([
            df.loc[i, 'equipment_name'],
            df.loc[i, 'maintenance_type'],
            x[i].varValue,
            df.loc[i, 'maintenance_cost'] * x[i].varValue,
            df.loc[i, 'maintenance_duration'] * x[i].varValue
        ])

    total_maintenance_cost = sum([df.loc[i, 'maintenance_cost'] * x[i].varValue for i in df.index])
    total_maintenance_duration = sum([df.loc[i, 'maintenance_duration'] * x[i].varValue for i in df.index])

    # Debugging des valeurs optimisées
    for i in df.index:
        print(f"{df.loc[i, 'equipment_name']} - maintenance: {x[i].varValue}, cost: {df.loc[i, 'maintenance_cost'] * x[i].varValue}, duration: {df.loc[i, 'maintenance_duration'] * x[i].varValue}")

    return optimized_maintenance, total_maintenance_cost, total_maintenance_duration



def optimize_production(df, optimization_type):
    # Remplissage des valeurs manquantes avec 0.0
    df = df.fillna(0.0)
    
    # Conversion des colonnes en float
    for col in ['production_quality', 'production_cost', 'productivity']:
        df[col] = df[col].astype(float)

    prob = pl.LpProblem("ProductionOptimization", pl.LpMinimize if optimization_type == "minimize_cost" else pl.LpMaximize)
    x = pl.LpVariable.dicts("production", df.index, lowBound=0, cat='Continuous')

    if optimization_type == "minimize_cost":
        prob += pl.lpSum([df.loc[i, 'production_cost'] * x[i] for i in df.index])
    elif optimization_type == "maximize_quality":
        prob += pl.lpSum([df.loc[i, 'production_quality'] * x[i] for i in df.index])
    elif optimization_type == "maximize_productivity":
        prob += pl.lpSum([df.loc[i, 'productivity'] * x[i] for i in df.index])

    prob.solve()

    optimized_production = []
    for i in df.index:
        optimized_production.append([
            df.loc[i, 'equipment_name'],
            x[i].varValue,
            df.loc[i, 'production_cost'] * x[i].varValue
        ])

    total_production_cost = sum([df.loc[i, 'production_cost'] * x[i].varValue for i in df.index])

    return optimized_production, total_production_cost

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/optimize_maintenance', methods=['GET', 'POST'])
def optimize_maintenance_route():
    if request.method == 'POST':
        try:
            optimization_type = request.form['optimization_type']
            max_maintenance_duration = float(request.form['max_maintenance_duration'])
        except ValueError:
            return render_template('optimize_maintenance.html', error="Veuillez entrer des valeurs valides pour les paramètres d'optimisation.")

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM maintenance")
            data = cur.fetchall()
            cur.close()

            if not data:
                return render_template('optimize_maintenance.html', error="Aucune donnée trouvée dans la table maintenance.")

            df = pd.DataFrame(data, columns=['id', 'equipment_name', 'maintenance_type', 'maintenance_cost', 'maintenance_duration', 'frequency', 'downtime_hours', 'downtime_cost', 'production_quality', 'production_hours', 'production_cost', 'availability', 'lifetime'])
            
            # Debugging des données
            print("Données récupérées:")
            print(df)

            optimized_maintenance, total_maintenance_cost, total_maintenance_duration = optimize_maintenance(df, optimization_type, max_maintenance_duration)

            return render_template('result_maintenance.html', optimized_maintenance=optimized_maintenance, total_maintenance_cost=total_maintenance_cost, total_maintenance_duration=total_maintenance_duration)

        except Exception as e:
            print(f"Erreur lors de la récupération des données : {str(e)}")
            return render_template('optimize_maintenance.html', error=f"Erreur lors de la récupération des données : {str(e)}")

    return render_template('optimize_maintenance.html')



@app.route('/optimize_production', methods=['GET', 'POST'])
def optimize_production_route():
    if request.method == 'POST':
        try:
            optimization_type = request.form['optimization_type']
        except ValueError:
            return render_template('optimize_production.html', error="Veuillez entrer des valeurs valides pour les paramètres d'optimisation.")

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM production")
            data = cur.fetchall()
            cur.close()

            if not data:
                return render_template('optimize_production.html', error="Aucune donnée trouvée dans la table production.")

            df = pd.DataFrame(data, columns=['id', 'equipment_name', 'production_quality', 'production_cost', 'productivity'])

            optimized_production, total_production_cost = optimize_production(df, optimization_type)

            return render_template('result_production.html', optimized_production=optimized_production, total_production_cost=total_production_cost)

        except Exception as e:
            print(f"Erreur lors de la récupération des données : {str(e)}")
            return render_template('optimize_production.html', error=f"Erreur lors de la récupération des données : {str(e)}")

    return render_template('optimize_production.html')

if __name__ == '__main__':
    app.run(debug=True)
