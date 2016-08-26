# all the imports
import os
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash
import json
import highlight
import math

class Cluster:
    def __init__(self, fix, number, items):
        self.fix = fix
        self.number = number
        self.items = items
        # self.diffs = diffs
        # self.diffs = [diff[0] in diff for diffs]
        # self.inputoutputIDs = [diff[1] in diff for diffs]
        # self.results = results

app = Flask(__name__)
app.config.from_object(__name__)
ordered_clusters = []
# codes = {}
# results = {}
json_data = {}
questions = {1:'accumulate-mistakes.json', 2:'G-mistakes.json', 3:'Product-mistakes.json', 4:'repeated-mistakes.json'}

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'flaskr.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))

app.config.from_envvar('FLASKR_SETTINGS', silent=True)

def get_coverage(question_number,entries):

    covered_bugs = 0
    for entry in entries:
        print(entry['cluster_id'],entry['text'])
        print(ordered_clusters[question_number][entry['cluster_id']].number)
        covered_bugs+=ordered_clusters[question_number][entry['cluster_id']].number
    total_bugs = 0
    for cluster in ordered_clusters[question_number]:
        print(cluster.number)#, cluster.cluster_id)
        total_bugs+=cluster.number
        #try: print(cluster.text)
        #except: print('no text')
    print(covered_bugs,total_bugs)
    return math.ceil(covered_bugs*100/total_bugs)

def get_fix(question_number, cluster_id):
    return ordered_clusters[question_number][cluster_id].fix

def get_diffs(question_number, fix):

    before_map = {}
    after_map = {}

    codes_aux = json_data[question_number]['codes']
    pairs_before_after = codes_aux.get(fix, [])
    # pairs_before_after = codes[question_number].get(fix, [])

    idx = 0
    for pair_before_after in pairs_before_after:
        before_map['example'+str(idx)] = pair_before_after[0]
        after_map['example'+str(idx)] = pair_before_after[1]
        inputoutputID = pair_before_after[2]
        idx = idx+1
    files = highlight.diff_files(before_map, after_map, 'full', inputoutputID)
    return files

def get_results(question_number, fix):
    json_data[question_number]




def prepare_question(question_number):

    # global codes
    # global results
    global json_data

    # codes_aux = {}
    # results_aux = {}
    ordered_clusters = []

    with open('data/'+questions[question_number]) as data_file:
    	data = json.load(data_file)

    dict = {}
    # dict2 = {}
    # dictOfIDtoInputOutput = {}

    clustered_items = {}
    items = {}
    for i in data:
        if (i['IsFixed'] == True):
            fix = i['UsedFix']
            fix = fix.replace('\\', '')
            dict[fix] = dict.get(fix, 0) + 1

            item = i
            file_before = i['before']
            file_after = i['SynthesizedAfter']
            filename = 'filename-' + str(i['Id'])
            diff_lines = highlight.diff_file(filename, file_before, file_after, 'full')
            item['diff_lines'] = diff_lines
            item['tests'] = i['failed'] # process later

            # print(diff.values())
            id = i['Id']
            items[id] = item
            if (fix in clustered_items.keys()):
                clustered_items[fix].append(item)
            else:
                clustered_items[fix] = [item]

    json_data[question_number] = items

    for key in dict.keys():
        arr = (key, dict.get(key))

        fix = arr[0]
        # files = get_diffs(question_number, fix)

        # failed = dict2.get(key)
        # failed_str = map(str, failed)
        # failed = '\n'.join(failed_str)

        # files = get_diffs(question_number, fix)
        # diffs = files.values()
        # results = get_results()

        items = clustered_items[fix]
        cluster = Cluster(fix=fix, number=arr[1], items=items)
        ordered_clusters.append(cluster)
        #ordered_clusters.append((fix, item[1], fix.count("Insert"), fix.count("Update"), fix.count("Delete"), filesSample.values()))


    ordered_clusters = sorted(ordered_clusters, key=lambda cluster: -cluster.number)

    return ordered_clusters

def init_app():
    global ordered_clusters
    ordered_clusters = {}

    for question_number in questions.keys():
        ordered_clusters[question_number] = prepare_question(question_number)

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def get_hints(question_number):
    #todo: add question number to schema and db.execute call
    db = get_db()
    cur = db.execute('select title, cluster_id, text from entries order by id desc')
    hints = cur.fetchall()
    return hints

@app.route('/<int:question_number>')
def show_question(question_number):
    return redirect(url_for('show_detail', question_number=question_number, cluster_id=0))

@app.route('/')
def show_entries():
    return redirect(url_for('show_detail', question_number=1, cluster_id=0))

@app.route('/<int:question_number>/<int:cluster_id>')
def show_detail(question_number, cluster_id):

    entries = get_hints(question_number)
    coverage_percentage = get_coverage(question_number, entries)

    return render_template('layout.html', question_name = questions[question_number], question_number = question_number, clusters = ordered_clusters[question_number], entries = entries, cluster_id=cluster_id, coverage_percentage=coverage_percentage)

@app.route('/delete', methods=['POST'])
def delete_hint():
    db = get_db()
    db.execute('delete from entries where cluster_id=' + request.form['cluster_id'] + ' and question_number=' + request.form['question_number'])
    db.commit()
    return redirect(url_for('show_detail', question_number=request.form['question_number'], cluster_id=request.form['cluster_id']))

@app.route('/add', methods=['POST'])
def add_hint():
    db = get_db()
    db.execute('insert into entries (title, cluster_id, question_number, text) values (?, ?, ?, ?)',
                 ['title', request.form['cluster_id'], request.form['question_number'], request.form['text']])
    db.commit()
    return redirect(url_for('show_detail', question_number=request.form['question_number'], cluster_id=request.form['cluster_id']))

if __name__ == '__main__':
    # initdb_command()
    init_app()
    port = int(os.environ.get('PORT', 5000))
    app.config.update(
        DEBUG=True,
        TEMPLATES_AUTO_RELOAD=True
    )
    app.run(host='0.0.0.0', port=port)
