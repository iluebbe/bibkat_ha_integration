#!/usr/bin/env python3
"""Generate template slot sensors for BibKat with support for different include styles."""

def generate_templates_merge_list():
    """Generate template configuration for !include_dir_merge_list format."""
    
    # Start with list item
    output = """# BibKat Template Sensors
# Diese Datei ist für !include_dir_merge_list formatiert
# Verwendung: template: !include_dir_merge_list templates/
# Speichern als: templates/02_bibkat.yaml

- sensor:"""
    
    # Generate all 30 slots
    for i in range(1, 31):
        index = i - 1
        output += f"""
    # Slot {i}
    - name: "Bibliothek Slot {i}"
      unique_id: bibkat_book_slot_{i}
      state: >
        {{% set books = states.button 
           | selectattr('entity_id', 'match', 'button.bibkat_.*') 
           | rejectattr('attributes.media_id', 'undefined')
           | sort(attribute='attributes.days_remaining') | list %}}
        {{{{ books[{index}].attributes.title if books[{index}] is defined else 'Leer' }}}}
      icon: >
        {{% set books = states.button 
           | selectattr('entity_id', 'match', 'button.bibkat_.*') 
           | rejectattr('attributes.media_id', 'undefined')
           | sort(attribute='attributes.days_remaining') | list %}}
        {{% if books[{index}] is defined %}}
          {{% set days = books[{index}].attributes.days_remaining %}}
          {{% if days < 0 %}}mdi:book-alert
          {{% elif days <= 3 %}}mdi:book-clock
          {{% else %}}mdi:book-check
          {{% endif %}}
        {{% else %}}mdi:book-off-outline
        {{% endif %}}
      attributes:
        entity_id: >
          {{% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}}
          {{{{ books[{index}].entity_id if books[{index}] is defined else 'none' }}}}
        days_remaining: >
          {{% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}}
          {{{{ books[{index}].attributes.days_remaining if books[{index}] is defined else 999 }}}}
        author: >
          {{% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}}
          {{{{ books[{index}].attributes.author if books[{index}] is defined else '' }}}}
        account: >
          {{% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}}
          {{{{ books[{index}].attributes.account_alias if books[{index}] is defined else '' }}}}
        renewable: >
          {{% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}}
          {{{{ books[{index}].attributes.is_renewable_now if books[{index}] is defined else false }}}}
        due_date: >
          {{% set books = states.button 
             | selectattr('entity_id', 'match', 'button.bibkat_.*') 
             | rejectattr('attributes.media_id', 'undefined')
             | sort(attribute='attributes.days_remaining') | list %}}
          {{{{ books[{index}].attributes.due_date if books[{index}] is defined else '' }}}}"""
    
    # Add statistics sensors
    output += """

    # Zusätzliche Template Sensoren für Statistiken
    - name: "Bibliothek Bücher Gesamt"
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

- binary_sensor:"""
    
    # Generate binary sensors for each slot
    for i in range(1, 31):
        # Overdue
        output += f"""
    - name: "Bibliothek Slot {i} Überfällig"
      unique_id: bibliothek_slot_{i}_uberfallig
      state: >
        {{{{ states('sensor.bibliothek_slot_{i}') != 'Leer' and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') is not none and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') | int(999) < 0 }}}}"""
        
        # Due soon
        output += f"""
    - name: "Bibliothek Slot {i} Bald Fällig"
      unique_id: bibliothek_slot_{i}_bald_fallig
      state: >
        {{{{ states('sensor.bibliothek_slot_{i}') != 'Leer' and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') is not none and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') | int(999) >= 0 and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') | int(999) <= 3 }}}}"""
        
        # Normal
        output += f"""
    - name: "Bibliothek Slot {i} Normal"
      unique_id: bibliothek_slot_{i}_normal
      state: >
        {{{{ states('sensor.bibliothek_slot_{i}') != 'Leer' and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') is not none and state_attr('sensor.bibliothek_slot_{i}', 'days_remaining') | int(999) > 3 }}}}"""
    
    return output

if __name__ == "__main__":
    # Generate the merge_list format
    template_content = generate_templates_merge_list()
    
    # Write to file
    with open("bibkat_template_slots_merge_list.yaml", "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print("Generated bibkat_template_slots_merge_list.yaml for !include_dir_merge_list!")