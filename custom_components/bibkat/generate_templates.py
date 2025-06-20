#!/usr/bin/env python3
"""Generate all 20 template slot sensors for BibKat."""

def generate_slot(slot_number, indent="    "):
    """Generate template configuration for a single slot."""
    # Use slot_number - 1 for array index
    index = slot_number - 1
    
    return f"""
{indent}# Slot {slot_number}
{indent}- name: "Bibliothek Slot {slot_number}"
{indent}  unique_id: bibkat_book_slot_{slot_number}
{indent}  state: >
{indent}    {{% set books = states.button 
{indent}       | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}       | rejectattr('attributes.media_id', 'undefined')
{indent}       | sort(attribute='attributes.days_remaining') | list %}}
{indent}    {{{{ books[{index}].attributes.title if books[{index}] is defined else 'Leer' }}}}
{indent}  icon: >
{indent}    {{% set books = states.button 
{indent}       | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}       | rejectattr('attributes.media_id', 'undefined')
{indent}       | sort(attribute='attributes.days_remaining') | list %}}
{indent}    {{% if books[{index}] is defined %}}
{indent}      {{% set days = books[{index}].attributes.days_remaining %}}
{indent}      {{% if days < 0 %}}mdi:book-alert
{indent}      {{% elif days <= 3 %}}mdi:book-clock
{indent}      {{% else %}}mdi:book-check
{indent}      {{% endif %}}
{indent}    {{% else %}}mdi:book-off-outline
{indent}    {{% endif %}}
{indent}  attributes:
{indent}    entity_id: >
{indent}      {{% set books = states.button 
{indent}         | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}         | rejectattr('attributes.media_id', 'undefined')
{indent}         | sort(attribute='attributes.days_remaining') | list %}}
{indent}      {{{{ books[{index}].entity_id if books[{index}] is defined else 'none' }}}}
{indent}    days_remaining: >
{indent}      {{% set books = states.button 
{indent}         | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}         | rejectattr('attributes.media_id', 'undefined')
{indent}         | sort(attribute='attributes.days_remaining') | list %}}
{indent}      {{{{ books[{index}].attributes.days_remaining if books[{index}] is defined else 999 }}}}
{indent}    author: >
{indent}      {{% set books = states.button 
{indent}         | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}         | rejectattr('attributes.media_id', 'undefined')
{indent}         | sort(attribute='attributes.days_remaining') | list %}}
{indent}      {{{{ books[{index}].attributes.author if books[{index}] is defined else '' }}}}
{indent}    account: >
{indent}      {{% set books = states.button 
{indent}         | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}         | rejectattr('attributes.media_id', 'undefined')
{indent}         | sort(attribute='attributes.days_remaining') | list %}}
{indent}      {{{{ books[{index}].attributes.account_alias if books[{index}] is defined else '' }}}}
{indent}    renewable: >
{indent}      {{% set books = states.button 
{indent}         | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}         | rejectattr('attributes.media_id', 'undefined')
{indent}         | sort(attribute='attributes.days_remaining') | list %}}
{indent}      {{{{ books[{index}].attributes.is_renewable_now if books[{index}] is defined else false }}}}
{indent}    due_date: >
{indent}      {{% set books = states.button 
{indent}         | selectattr('entity_id', 'match', 'button.bibkat_.*') 
{indent}         | rejectattr('attributes.media_id', 'undefined')
{indent}         | sort(attribute='attributes.days_remaining') | list %}}
{indent}      {{{{ books[{index}].attributes.due_date if books[{index}] is defined else '' }}}}"""

def generate_category_sensor(slot_number, category, indent="    "):
    """Generate binary sensor for slot categorization."""
    sensor_id = f"bibliothek_slot_{slot_number}_{category}"
    
    if category == "uberfallig":
        name = f"Bibliothek Slot {slot_number} Überfällig"
        condition = f"states('sensor.bibliothek_slot_{slot_number}') != 'Leer' and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') is not none and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') | int(999) < 0"
    elif category == "bald_fallig":
        name = f"Bibliothek Slot {slot_number} Bald Fällig"
        condition = f"states('sensor.bibliothek_slot_{slot_number}') != 'Leer' and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') is not none and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') | int(999) >= 0 and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') | int(999) <= 3"
    else:  # normal
        name = f"Bibliothek Slot {slot_number} Normal"
        condition = f"states('sensor.bibliothek_slot_{slot_number}') != 'Leer' and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') is not none and state_attr('sensor.bibliothek_slot_{slot_number}', 'days_remaining') | int(999) > 3"
    
    return f"""
{indent}- name: "{name}"
{indent}  unique_id: {sensor_id}
{indent}  state: >
{indent}    {{{{ {condition} }}}}"""

def generate_full_template(format_type="include"):
    """Generate the complete template configuration.
    
    Args:
        format_type: "include" for !include style, "merge_list" for !include_dir_merge_list style
    """
    if format_type == "merge_list":
        # Format for !include_dir_merge_list
        output = """# BibKat Template Sensors
# Diese Datei ist für !include_dir_merge_list formatiert
# Verwendung in configuration.yaml:
#   template: !include_dir_merge_list templates/
# Dann diese Datei als templates/02_bibkat.yaml speichern

- sensor:"""
    else:
        # Original format for !include
        output = """# BibKat Template Sensors
# Diese Datei kann direkt in die configuration.yaml eingebunden werden:
#
# template:
#   - !include bibkat_template_slots.yaml
#
# Oder wenn Sie bereits andere template-Dateien haben:
# template:
#   - !include ihre_andere_template.yaml
#   - !include bibkat_template_slots.yaml

sensor:"""
    
    # Generate all 30 slots
    indent = "      " if format_type == "merge_list" else "    "
    for i in range(1, 31):
        output += generate_slot(i, indent)
    
    # Add statistics sensors
    if format_type == "merge_list":
        output += f"""

{indent}# Zusätzliche Template Sensoren für Statistiken
{indent}- name: "Bibliothek Bücher Gesamt"
      unique_id: bibkat_total_books
      state: >
        {{ states.button 
           | selectattr('entity_id', 'match', 'button.bibkat_.*') 
           | rejectattr('attributes.media_id', 'undefined')
           | list | length }}
      unit_of_measurement: "Bücher"
      icon: mdi:bookshelf

    - name: "Bibliothek Überfällige Bücher"
      unique_id: bibkat_overdue_books
      state: >
        {{ states.button 
           | selectattr('entity_id', 'match', 'button.bibkat_.*') 
           | rejectattr('attributes.media_id', 'undefined')
           | selectattr('attributes.days_remaining', 'lt', 0)
           | list | length }}
      unit_of_measurement: "Bücher"
      icon: mdi:book-alert

    - name: "Bibliothek Verlängerbare Bücher"
      unique_id: bibkat_renewable_books
      state: >
        {{ states.button 
           | selectattr('entity_id', 'match', 'button.bibkat_.*') 
           | rejectattr('attributes.media_id', 'undefined')
           | selectattr('attributes.is_renewable_now', 'eq', true)
           | list | length }}
      unit_of_measurement: "Bücher"
      icon: mdi:book-refresh

    - name: "Bibliothek Nächste Rückgabe"
      unique_id: bibkat_next_due
      state: >
        {% set books = states.button 
           | selectattr('entity_id', 'match', 'button.bibkat_.*') 
           | rejectattr('attributes.media_id', 'undefined')
           | sort(attribute='attributes.days_remaining') | list %}
        {{ books[0].attributes.days_remaining if books[0] is defined else 999 }}
      unit_of_measurement: "Tage"
      icon: mdi:calendar-clock
      attributes:
        title: >
          {% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}
          {{ books[0].attributes.title if books[0] is defined else 'Keine Bücher' }}

    - name: "Bibliothek Vormerkungen Gesamt"
      unique_id: bibkat_total_reservations
      state: >
        {% set reservation_sensors = states.sensor 
           | selectattr('entity_id', 'match', 'sensor.bibkat_.*vormerkungen.*')
           | list %}
        {% if reservation_sensors %}
          {{ reservation_sensors | map(attribute='state') | select('number') | map('int') | sum }}
        {% else %}
          0
        {% endif %}
      unit_of_measurement: "Vormerkungen"
      icon: mdi:bookmark-multiple

binary_sensor:"""
    
    # Generate binary sensors for each slot and category
    for i in range(1, 31):
        output += generate_category_sensor(i, "uberfallig")
        output += generate_category_sensor(i, "bald_fallig")
        output += generate_category_sensor(i, "normal")
    
    return output

if __name__ == "__main__":
    # Generate the full template
    template_content = generate_full_template()
    
    # Write to file
    with open("bibkat_template_slots.yaml", "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print("Generated bibkat_template_slots.yaml with all 30 slots!")