from __future__ import annotations
from typing import TYPE_CHECKING, Sequence, Any
if TYPE_CHECKING:
    from sqlalchemy import Engine

import streamlit as st
from sqlalchemy import text, Row
from database import Database
from datetime import date

@st.cache_resource
def _get_database() -> Database:
    return Database()

class StreamlitMode:
    NameInputStandard = 1
    NameInputNewCompany = 2
    FullList = 3

def ShowDate() -> None:
    st.session_state.setdefault('selectedDate', date.today())
    left, right = st.columns([2, 1], vertical_alignment='bottom')
    with left:
        st.date_input('Date', label_visibility='visible', format='DD/MM/YYYY', key='selectedDate')
    with right:
        st.button('Show all for this date', use_container_width=True, on_click=lambda: setattr(st.session_state, 'Mode', StreamlitMode.FullList))

def ShowCompany() -> None:
    sql = (
        "WITH companies AS (SELECT entity_id FROM entities WHERE entity_type = 'Company') "
        "SELECT companies.entity_id, properties.property_value FROM companies LEFT JOIN properties ON companies.entity_id = properties.entity_id "
        "WHERE properties.property_name = 'Name'"
    )
    company_names = [f'{itm.entity_id} | {itm.property_value}' for itm in db.query(sql)]
    st.selectbox('Company name', company_names + ['Add New'], label_visibility='visible', key = 'selectedCompany')

@st.cache_data(ttl=60)
def _get_personnel_for_company(company_name:str) -> Sequence[Row[Any]]:
    sql = (
        "WITH "
            "people AS (SELECT entity_id FROM entities WHERE entity_type = 'Person'), "
            "company AS (SELECT entity_id FROM entities WHERE entity_type = 'Company'), "
            "selectedCompany AS (SELECT company.entity_id FROM company "
                "LEFT JOIN properties ON company.entity_id = properties.entity_id "
                "WHERE property_name = 'Name' AND property_value = :selectedCompany), "
            "selectedCompanyPersonellIDS AS (SELECT people.entity_id FROM people "
                "LEFT JOIN properties ON people.entity_id = properties.entity_id "
                "WHERE property_name = 'Company' AND property_value::INTEGER = (SELECT entity_id FROM selectedCompany)), "
            "selectedCompanyPersonellNames AS (SELECT scp.entity_id, property_name,property_value FROM selectedCompanyPersonellIDS AS scp "
                "LEFT JOIN properties ON scp.entity_id = properties.entity_id "
                "WHERE property_name = 'First Name' OR property_name = 'Last Name') "
        "SELECT entity_id, "
            "MAX(CASE WHEN property_name = 'First Name' THEN property_value END) AS \"first_name\", "
            "MAX(CASE WHEN property_name = 'Last Name' THEN property_value END) AS \"last_name\" "
            "FROM selectedCompanyPersonellNames "
            "GROUP BY entity_id"
    )
    params = {'selectedCompany': company_name}
    return db.query(sql, params)

def ShowExistingPersonell() -> None:
    company_name = st.session_state.selectedCompany.split('|')[1].strip()
    st.session_state.existingPersonell = _get_personnel_for_company(company_name)

    selected = []
    for person in st.session_state.existingPersonell:
        if st.checkbox(f'{person.entity_id} | {person.first_name} {person.last_name}', key=f'person_{person.entity_id}'):
            selected.append(person.entity_id)
    st.session_state.selectedExistingPeople = selected

def AddNewPersonell() -> None:
    st.session_state.newPersonell.append({
        'First Name': st.session_state.firstName,
        'Last Name':st.session_state.lastName
    })
    st.session_state.firstName = ''
    st.session_state.lastName = ''

def ShowNewPersonell() -> None:
    left, middle, right = st.columns([4, 4, 1], vertical_alignment='bottom')
    with left:
        st.text_input('First Name', label_visibility='visible', key='firstName')
    with middle:
        st.text_input('Last Name', label_visibility='visible', key='lastName')
    with right:
        st.button('Add', use_container_width=True, on_click=AddNewPersonell)
    if len(st.session_state.newPersonell) > 0:
        st.dataframe(st.session_state.newPersonell, hide_index=True)

def AddNewCompany() -> None:
    sql = "INSERT INTO entities (entity_type) VALUES ('Company') RETURNING entity_id"
    company_id = db.execute(sql)[0].entity_id
    sql = "INSERT INTO properties (entity_id, property_name, property_value, value_type) VALUES (:entity_id, 'Name', :property_value, 'text')"
    params = {'entity_id': company_id, 'property_value': st.session_state.newCompany}
    db.execute(sql, params)
    st.session_state.selectedCompany = f'{company_id} | {st.session_state.newCompany}'
    st.session_state.newCompany = ''
    st.session_state.Mode = StreamlitMode.NameInputStandard

def ShowNewCompany() -> None:
    st.text_input('Company', label_visibility='visible', key='newCompany')
    st.button('Add', use_container_width=True, on_click=AddNewCompany)

def Submit() -> None:
    # Add new person to the database and get their ID
    sql_addNewPerson = (
        "WITH "
            "companies AS (SELECT entity_id FROM entities WHERE entity_type = 'Company'), "
            "companyID as (SELECT companies.entity_id FROM companies "
                "LEFT JOIN properties ON companies.entity_id = properties.entity_id "
                "WHERE property_name = 'Name' AND property_value = :company_name), "
            "personID AS (INSERT INTO entities (entity_type) VALUES ('Person') RETURNING entity_id), "
            "personProperties AS (INSERT INTO properties (entity_id, property_name, property_value, value_type) "
            "VALUES ((SELECT entity_id FROM personID), 'Company', (SELECT entity_id::TEXT FROM companyID), 'entity_ref'), "
                "((SELECT entity_id FROM personID), 'First Name', :first_name, 'text'), "
                "((SELECT entity_id FROM personID), 'Last Name', :last_name, 'text'), "
                "((SELECT entity_id FROM personID), 'Position', '', 'text'), "
                "((SELECT entity_id FROM personID), 'Signed H&S', 'FALSE', 'text'), "
                "((SELECT entity_id FROM personID), 'Documented', 'FALSE', 'text')) "
        "SELECT entity_id FROM personID"
    )
    # Log their presence
    sql_logPresence = (
        "WITH "
            "presenceID AS (INSERT INTO entities (entity_type) VALUES ('Daily Presence') RETURNING entity_id) "
        "INSERT INTO properties (entity_id, property_name, property_value, value_type) "
        "VALUES ((SELECT entity_id FROM presenceID), 'Date', :date, 'text'), "
            "((SELECT entity_id FROM presenceID), 'Person', :personID, 'entity_ref')"
    )
    for person in st.session_state.newPersonell:
        params_addNewPerson = {
            'company_name': st.session_state.selectedCompany.split('|')[1].strip(),
            'first_name': person['First Name'],
            'last_name': person['Last Name']
        }
        personID = db.execute(sql_addNewPerson, params_addNewPerson)[0].entity_id
        params_logPresence = {
            'date': st.session_state.selectedDate.isoformat(),
            'personID': str(personID)
        }
        db.execute(sql_logPresence, params_logPresence)
    
    # Existing people are already in the database, so log their presence
    sql = (
        "WITH "
            "presenceID AS (INSERT INTO entities (entity_type) VALUES ('Daily Presence') RETURNING entity_id) "
        "INSERT INTO properties (entity_id, property_name, property_value, value_type) "
        "VALUES ((SELECT entity_id FROM presenceID), 'Date', :date, 'text'), "
            "((SELECT entity_id FROM presenceID), 'Person', :personID, 'entity_ref')"
    )
    for personID in st.session_state.selectedExistingPeople:
        params = {'date': st.session_state.selectedDate.isoformat(), 'personID': str(personID)}
        db.execute(sql, params)
    
    for var in st.session_state.keys():
        if isinstance(var, str) and var.startswith('person_'):
            st.session_state[var] = False
    
    ResetStateVariables()
    _get_personnel_for_company.clear()

def ShowAll() -> None:
    sql = (
        "WITH "
            "dpIDs AS (SELECT entity_id FROM entities WHERE entity_type = 'Daily Presence'), "
            "dpIDsDate AS (SELECT dpIDs.entity_id FROM dpIDs LEFT JOIN properties ON dpIDs.entity_id = properties.entity_id WHERE property_name = 'Date' and property_value = :selected_date), "
            "peopleIDsDate AS (SELECT property_value::INTEGER FROM dpIDsDate LEFT JOIN properties ON dpIDsDate.entity_id = properties.entity_id WHERE property_name = 'Person'), "
            "people AS (SELECT entity_id, property_name, properties.property_value, value_type FROM peopleIDsDate LEFT JOIN properties ON peopleIDsDate.property_value = properties.entity_id), "
            "peoplePivot AS (SELECT "
                    "entity_id AS \"Person ID\", "
                    "MAX(CASE WHEN property_name = 'First Name' THEN property_value END) AS \"First Name\", "
                    "MAX(CASE WHEN property_name = 'Last Name' THEN property_value END) AS \"Last Name\", "
                    "MAX(CASE WHEN property_name = 'Company' THEN property_value::INTEGER END) AS \"Company\", "
                    "MAX(CASE WHEN property_name = 'Position' THEN property_value END) AS \"Position\", "
                    "MAX(CASE WHEN property_name = 'Signed H&S' THEN property_value END) AS \"Signed H&S\", "
                    "MAX(CASE WHEN property_name = 'Documented' THEN property_value END) AS \"Documented\" "
                "FROM people "
                "GROUP BY entity_id) "
        "SELECT \"Person ID\", \"First Name\", \"Last Name\", property_value AS \"Company\", \"Position\", \"Signed H&S\", \"Documented\" "
        "FROM peoplePivot LEFT JOIN properties ON peoplePivot.\"Company\" = properties.entity_id where property_name = 'Name'"
    )
    params = {'selected_date': st.session_state.selectedDate.isoformat()}

    people = db.query(sql, params)
    st.button('Back', on_click=lambda: setattr(st.session_state,'Mode', StreamlitMode.NameInputStandard))
    st.dataframe(people, hide_index=True)

def ShowSubmitButton() -> None:
    st.button('Submit', on_click=Submit)

def SetUpStateVariables() -> None:
    if 'Mode' not in st.session_state:
        st.session_state.Mode = StreamlitMode.NameInputStandard
    if 'PreviousMode' not in st.session_state:
        st.session_state.PreviousMode = StreamlitMode.NameInputStandard
    if 'existingPersonell' not in st.session_state:
        st.session_state.existingPersonell = []
    if 'selectedExistingPeople' not in st.session_state:
        st.session_state.selectedExistingPeople = None
    if 'newPersonell' not in st.session_state:
        st.session_state.newPersonell = []
    if 'newCompanyPersonell' not in st.session_state:
        st.session_state.newCompanyPersonell = []

def ResetStateVariables() -> None:
    st.session_state.existingPersonell = []
    st.session_state.selectedExistingPeople = None
    st.session_state.newPersonell = []
    st.session_state.newCompanyPersonell = []

db = _get_database()
# First, set up all state variable, including modes
SetUpStateVariables()
# Secondly, reset state variable, except for modes, if mode changes
if st.session_state.Mode != st.session_state.PreviousMode:
    ResetStateVariables()
    st.session_state.PreviousMode = st.session_state.Mode
# Plot title
st.title('Presence log')

people, vehicles, overview = st.tabs(['People', 'Vehicles', 'Overview'])
with people:
    if st.session_state.Mode == StreamlitMode.NameInputStandard:
        ShowDate()
        ShowCompany()
        if st.session_state.selectedCompany == 'Add New':
            st.session_state.Mode = StreamlitMode.NameInputNewCompany
            st.rerun()
        ShowExistingPersonell()
        ShowNewPersonell()
        ShowSubmitButton()
    elif st.session_state.Mode == StreamlitMode.NameInputNewCompany:
        ShowDate()
        ShowCompany()
        if st.session_state.selectedCompany != 'Add New':
            st.session_state.Mode = StreamlitMode.NameInputStandard
            st.rerun()
        ShowNewCompany()
    elif st.session_state.Mode == StreamlitMode.FullList:
        ShowAll()
with vehicles:
    pass
with overview:
    ShowAll()
