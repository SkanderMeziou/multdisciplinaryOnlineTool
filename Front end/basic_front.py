from pathlib import Path

# Path to the directory containing the data
researcher_file = Path('../PER_temp_files/data/all_authors.csv')
phd_file = Path('../PER_temp_files/data/theses.csv')
input_file = Path('../PER_temp_files/data/fake_data.csv')

output_file = Path('../Back end/templates')
output_file.mkdir(parents=True, exist_ok=True)

# Write main html page
with open(output_file / 'index.html', 'w') as f:
    f.write("""
    <html>
    <head>
        <title>View Phd students</title>
        <base href="..">
        <style>
            body {
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body>
    """)

# Add a search bar linked to the table phd_file
with open(output_file / 'index.html', 'a') as f:
    f.write(f"""
        <h3>
          Search for PhD Student
          <span class="htmx-indicator">
            <img src="/img/bars.svg"/> Searching...
           </span>
        </h3>
        <input class="form-control" type="search"
               name="search" placeholder="Begin Typing To Search Student..."
               hx-post="/search"
               hx-trigger="input changed delay:500ms, keyup[key=='Enter'], load"
               hx-target="#search-results"
               hx-indicator=".htmx-indicator">
        
        <table class="table">
            <thead>
            <tr>
              <th>First Name</th>
              <th>Last Name</th>
              <th>Email</th>
            </tr>
            </thead>
            <tbody id="search-results">
            </tbody>
        </table>
    """)

# Finish the html page
with open(output_file / 'index.html', 'a') as f:
    f.write("""
    </body>
    </html>
    """)