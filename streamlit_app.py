from __future__ import annotations
from typing import TYPE_CHECKING, Sequence, Any
if TYPE_CHECKING:
    from sqlalchemy import Engine

import streamlit as st
from sqlalchemy import text, Row
from database import Database
from datetime import date
import pandas as pd
from streamlitmodes import StreamlitMode

@st.cache_resource
def _get_database() -> Database:
    return Database()

@st.cache_data(ttl=60)
def _get_companies() -> pd.DataFrame:
    sql = """
        SELECT e.entity_id AS company_id, p.property_value AS company_name FROM entities e LEFT JOIN properties p ON e.entity_id = p.entity_id
        WHERE e.entity_type = 'Company' AND property_name = 'Name'
        ORDER BY p.property_value
    """
    companies = pd.DataFrame(db.query(sql))
    if companies.empty:
        return pd.DataFrame(columns=['company_id', 'company_name'])
    width = len(str(companies['company_id'].max()))
    companies['company_id'] = companies['company_id'].apply(lambda x: str(x).zfill(width))
    return companies

@st.cache_data(ttl=60)
def _get_personnel_for_company(company_id:int) -> pd.DataFrame:
    sql = """
        SELECT
            e.entity_id AS person_id,
            MIN(CASE WHEN pr.property_name = 'First Name' THEN pr.property_value END) AS "First Name",
            MIN(CASE WHEN pr.property_name = 'Last Name' THEN pr.property_value END) AS "Last Name",
            MIN(CASE WHEN pr.property_name = 'Position' THEN pr.property_value END) AS "Position",
            MIN(CASE WHEN pr.property_name = 'Signed H&S' THEN pr.property_value END) AS "Signed H&S",
            MIN(CASE WHEN pr.property_name = 'Documented' THEN pr.property_value END) AS "Documented"
        FROM entities e
        INNER JOIN properties p ON e.entity_id = p.entity_id AND e.entity_type = 'Person' AND p.property_name = 'Company' AND p.property_value::INTEGER = :company_id
        LEFT JOIN properties pr ON pr.entity_id = e.entity_id
        GROUP BY e.entity_id
    """
    params = {'company_id': company_id}
    personnel = pd.DataFrame(db.query(sql, params))
    if personnel.empty:
        return pd.DataFrame(columns=['person_id', 'First Name', 'Last Name', 'Position', 'Signed H&S', 'Documented'])
    width = len(str(personnel['person_id'].max()))
    personnel['person_id'] = personnel['person_id'].apply(lambda x: str(x).zfill(width))
    return personnel

@st.cache_data(ttl=60)
def _get_company_and_type_for_vehicle(regNo:str) -> tuple[pd.DataFrame,pd.DataFrame]:
    sql = """
        SELECT e.entity_id AS ent_id FROM entities e LEFT JOIN properties p ON e.entity_id = p.entity_id
        WHERE e.entity_type = 'Vehicle' AND p.property_name = 'Registration No.' AND p.property_value = :regNo
    """
    params = {'regNo': regNo}
    ent_id = db.query(sql, params)
    if len(ent_id) == 0:
        return pd.DataFrame(columns=['vehicle_type']), pd.DataFrame(columns=['company_id', 'company_name'])
    else:
        ent_id = ent_id[0].ent_id
    sql = """
        SELECT properties.property_value AS vehicle_type FROM properties
        WHERE properties.entity_id = :ent_id AND properties.property_name = 'Type'
    """
    params = {'ent_id': ent_id}
    vehicle_types = pd.DataFrame(db.query(sql, params))
    if vehicle_types.empty:
        vehicle_types = pd.DataFrame(columns=['vehicle_type'])
    sql = """
        SELECT DISTINCT pr.property_value::INTEGER AS company_id, pro.property_value AS company_name FROM entities e
        INNER JOIN properties p ON e.entity_id = p.entity_id AND e.entity_type = 'Daily Presence' AND p.property_name = 'Vehicle' AND p.property_value::INTEGER = :ent_id
        INNER JOIN properties pr ON e.entity_id = pr.entity_id AND (pr.property_name = 'Company' OR pr.property_name = 'Proxy Company') AND pr.property_value <> ''
        INNER JOIN properties pro ON pr.property_value::INTEGER = pro.entity_id AND pro.property_name = 'Name'
    """
    params = {'ent_id': ent_id}
    companies = pd.DataFrame(db.query(sql, params))
    if companies.empty:
        companies = pd.DataFrame(columns=['company_id', 'company_name'])
    width = len(str(companies['company_id'].max()))
    companies['company_id'] = companies['company_id'].apply(lambda x: str(x).zfill(width))
    return vehicle_types, companies

@st.cache_data(ttl=60)
def _get_vehicle_types() -> pd.DataFrame:
    basic_types = ['Εκσκαφέας', 'Αεροσυμπιεστής', 'Δονητής', 'Αναμικτήρας μπετόν', 'Γερανός', 'Βίντζι', 
        'Φορτηγό', 'Οδοστρωτήρας', 'Συμπυκνωτής', 'Τηλεσκοπικό', 'Αναβατόριο', 'Γεννήτρια', 
        'Μηχανή για κόψιμο Σίδερων', 'Μηχανή για Λύγισμα Σίδερων']
    sql = """
        SELECT DISTINCT(properties.property_value) AS vehicle_type FROM
            (SELECT entity_id FROM entities WHERE entity_type = 'Vehicle') AS tmp
        LEFT JOIN properties ON tmp.entity_id = properties.entity_id
        WHERE properties.property_name = 'Type'
    """
    vehicle_types = pd.DataFrame(db.query(sql))
    basic_types = pd.DataFrame([{'vehicle_type': itm} for itm in basic_types])
    vehicle_types = pd.concat([vehicle_types, basic_types])
    vehicle_types = vehicle_types.drop_duplicates(subset='vehicle_type').sort_values('vehicle_type')
    return vehicle_types

def ShowDate() -> None:
    if st.session_state.Reruns == 1:
        st.session_state.selectedDate = date.today()
    st.date_input('Date', label_visibility='visible', format='DD/MM/YYYY', key='selectedDate')

def ShowCompany() -> None:
    companies = _get_companies()
    company_names = (companies['company_id'] + '. ' + companies['company_name']).tolist()
    st.selectbox('Company name', company_names + ['Add New'], label_visibility='visible', key = 'selectedCompany')

def ShowExistingpersonnel() -> None:
    company_id = int(st.session_state.selectedCompany.split('. ')[0].strip())
    personnel = _get_personnel_for_company(company_id)
    personnelLabels = personnel['person_id'] + '. ' + personnel['First Name'] + ' ' + personnel['Last Name']

    selected = []
    for person_id, personLabel in zip(personnel['person_id'].tolist(), personnelLabels):
        if st.checkbox(personLabel, key=f'person_{person_id}'):
            selected.append(person_id)
    st.session_state.selectedExistingPeople = selected

def AddNewpersonnel() -> None:
    st.session_state.newpersonnel.append({
        'First Name': st.session_state.firstName,
        'Last Name':st.session_state.lastName
    })
    st.session_state.firstName = ''
    st.session_state.lastName = ''

def ShowNewpersonnel() -> None:
    left, middle, right = st.columns([4, 4, 1], vertical_alignment='bottom')
    with left:
        st.text_input('First Name', label_visibility='visible', key='firstName')
    with middle:
        st.text_input('Last Name', label_visibility='visible', key='lastName')
    with right:
        st.button('Add', use_container_width=True, on_click=AddNewpersonnel)
    if len(st.session_state.newpersonnel) > 0:
        st.dataframe(st.session_state.newpersonnel, hide_index=True)

def AddNewCompany() -> None:
    sql = """
        WITH ent_id AS (INSERT INTO entities (entity_type) VALUES ('Company') RETURNING entity_id)
        INSERT INTO properties (entity_id, property_name, property_value, value_type)
        VALUES ((SELECT entity_id from ent_id), 'Name', :company_name, 'text') RETURNING entity_id
    """
    params = {'company_name': st.session_state.newCompany}
    company_id = db.execute(sql, params)[0].entity_id
    width = max(len(str(_get_companies()['company_id'].max())), len(str(company_id)))
    st.session_state.selectedCompany = str(company_id).zfill(width) + '. ' + st.session_state.newCompany
    st.session_state.newCompany = ''
    st.session_state.Mode = StreamlitMode.NameInputStandard
    _get_companies.clear()

def ShowNewCompany() -> None:
    st.text_input('Company', label_visibility='visible', key='newCompany')
    st.button('Add', use_container_width=True, on_click=AddNewCompany)

def SubmitPeople() -> None:
    # Add new person to the database and log their presence
    sql_newPerson = """
        WITH
            person_id AS (INSERT INTO entities (entity_type) VALUES ('Person') RETURNING entity_id),
            person_properties AS (INSERT INTO properties (entity_id, property_name, property_value, value_type)
                VALUES ((SELECT entity_id FROM person_id), 'Company', :company_id, 'entity_ref'),
                    ((SELECT entity_id FROM person_id), 'First Name', :first_name, 'text'),
                    ((SELECT entity_id FROM person_id), 'Last Name', :last_name, 'text'),
                    ((SELECT entity_id FROM person_id), 'Position', '', 'text'),
                    ((SELECT entity_id FROM person_id), 'Signed H&S', 'FALSE', 'text'),
                    ((SELECT entity_id FROM person_id), 'Documented', 'FALSE', 'text')),
            daily_presence_id AS (INSERT INTO entities (entity_type) VALUES ('Daily Presence') RETURNING entity_id)
        INSERT INTO properties (entity_id, property_name, property_value, value_type)
        VALUES ((SELECT entity_id FROM daily_presence_id), 'Date', :date, 'text'),
            ((SELECT entity_id FROM daily_presence_id), 'Person', (SELECT entity_id::TEXT FROM person_id), 'entity_ref')
    """
    for person in st.session_state.newpersonnel:
        params_newPerson = {
            'company_id': str(int(st.session_state.selectedCompany.split('.')[0].strip())),
            'first_name': person['First Name'],
            'last_name': person['Last Name'],
            'date': st.session_state.selectedDate.isoformat()
        }
        db.execute(sql_newPerson, params_newPerson)
    
    # Existing people are already in the database, so log their presence
    sql = """
        WITH
            daily_presence_id AS (INSERT INTO entities (entity_type) VALUES ('Daily Presence') RETURNING entity_id)
        INSERT INTO properties (entity_id, property_name, property_value, value_type)
        VALUES ((SELECT entity_id from daily_presence_id), 'Date', :date, 'text'),
            ((SELECT entity_id from daily_presence_id), 'Person', :person_id, 'entity_ref')
    """
    for personID in st.session_state.selectedExistingPeople:
        params = {
            'date': st.session_state.selectedDate.isoformat(),
            'person_id': str(personID)
        }
        db.execute(sql, params)
    
    for var in st.session_state.keys():
        if isinstance(var, str) and var.startswith('person_'):
            st.session_state[var] = False
    
    ResetStateVariables()
    _get_personnel_for_company.clear()

def ShowAllPeople() -> None:
    sql = """
        SELECT "Date", "Person ID", "First Name", "Last Name", properties.property_value AS "Company", "Position", "Documented", "Signed H&S" FROM
        (SELECT
            MIN(tmp.date) AS "Date",
            tmp.person_id AS "Person ID",
            MIN(CASE WHEN properties.property_name = 'First Name' THEN properties.property_value END) AS "First Name",
            MIN(CASE WHEN properties.property_name = 'Last Name' THEN properties.property_value END) AS "Last Name",
            MIN(CASE WHEN properties.property_name = 'Company' THEN properties.property_value::INTEGER END) AS company_id,
            MIN(CASE WHEN properties.property_name = 'Position' THEN properties.property_value END) AS "Position",
            MIN(CASE WHEN properties.property_name = 'Documented' THEN properties.property_value END) AS "Documented",
            MIN(CASE WHEN properties.property_name = 'Signed H&S' THEN properties.property_value END) AS "Signed H&S"
        FROM
            (SELECT
            MIN(CASE WHEN properties.property_name = 'Date' THEN properties.property_value END) AS date,
            MIN(CASE WHEN properties.property_name = 'Person' THEN properties.property_value::INTEGER END) AS person_id
            FROM
            (SELECT tmp.entity_id FROM
                (SELECT entity_id FROM entities WHERE entity_type = 'Daily Presence') AS tmp
            LEFT JOIN properties ON tmp.entity_id = properties.entity_id AND ((properties.property_name = 'Date' AND properties.property_value = :date) OR properties.property_name = 'Person')
            GROUP BY tmp.entity_id
            HAVING COUNT(*) = 2) AS tmp
            LEFT JOIN properties ON tmp.entity_id = properties.entity_id
            GROUP BY tmp.entity_id) AS tmp
        LEFT JOIN properties ON tmp.person_id = properties.entity_id
        GROUP BY tmp.person_id) AS tmp
        LEFT JOIN properties ON tmp.company_id = properties.entity_id
        WHERE properties.property_name = 'Name'
    """
    params = {'date': st.session_state.selectedDate.isoformat()}
    st.header('People')
    st.dataframe(db.query(sql, params), hide_index=True)

def ShowAllVehicles() -> None:
    sql = """
        SELECT
        tmp.entity_id AS "Presence Record ID",
        MIN(CASE WHEN tmp.property_name = 'Date' THEN tmp.property_value END) AS "Date",
        MIN(CASE WHEN tmp.property_name = 'Vehicle' THEN tmp.property_value END) AS "Registration No.",
        MIN(CASE WHEN tmp.property_name = 'Company' THEN tmp.property_value END) AS "Company",
        MIN(CASE WHEN tmp.property_name = 'Proxy Company' THEN tmp.property_value END) AS "Proxy Company"
        FROM
        (SELECT
            tmp.entity_id,
            tmp.property_name,
            CASE
            WHEN tmp.property_name = 'Vehicle' THEN p_v.property_value
            WHEN tmp.property_name = 'Company' THEN (CASE WHEN tmp.property_value = '' THEN '' ELSE p_c.property_value END)
            WHEN tmp.property_name = 'Proxy Company' THEN (CASE WHEN tmp.property_value = '' THEN '' ELSE p_pc.property_value END)
            ELSE tmp.property_value
            END
        FROM
            (SELECT tmp.entity_id, properties.property_name, properties.property_value FROM
            (SELECT tmp.entity_id FROM
                (SELECT entity_id FROM entities WHERE entity_type = 'Daily Presence') AS tmp
            LEFT JOIN properties ON tmp.entity_id = properties.entity_id AND ((properties.property_name = 'Date' AND properties.property_value = :date) OR properties.property_name = 'Vehicle')
            GROUP BY tmp.entity_id
            HAVING COUNT(*) = 2) AS tmp
            LEFT JOIN properties ON tmp.entity_id = properties.entity_id) AS tmp
        LEFT JOIN properties p_v ON tmp.property_name = 'Vehicle' AND (CASE WHEN tmp.property_name = 'Vehicle' THEN tmp.property_value::INTEGER END) = p_v.entity_id AND p_v.property_name = 'Registration No.'
        LEFT JOIN properties p_c ON tmp.property_name = 'Company' AND tmp.property_value <> '' AND (CASE WHEN tmp.property_name = 'Company' THEN tmp.property_value::INTEGER END) = p_c.entity_id AND p_c.property_name = 'Name'
        LEFT JOIN properties p_pc ON tmp.property_name = 'Proxy Company' AND tmp.property_value <> '' AND (CASE WHEN tmp.property_name = 'Proxy Company' THEN tmp.property_value::INTEGER END) = p_pc.entity_id AND p_pc.property_name = 'Name') AS tmp
        GROUP BY tmp.entity_id
    """
    params = {'date': st.session_state.selectedDate.isoformat()}
    st.header('Vehicles')
    st.dataframe(db.query(sql, params), hide_index=True)

def AddVehicle() -> None:
    if st.session_state.vehicleRegistrationNo == '':
        return
    regNo = st.session_state.vehicleRegistrationNo
    if st.session_state.vehicleTypeExisting == 'Add New...':
        typ = st.session_state.vehicleTypeNew
    else:
        typ = st.session_state.vehicleTypeExisting
    # Add the vehicle, if not existing
    sql = """
        SELECT t.entity_id FROM
            (SELECT entity_id FROM entities WHERE entity_type = 'Vehicle') AS t
        LEFT JOIN properties p ON t.entity_id = p.entity_id
        WHERE property_name = 'Registration No.' AND property_value = :regNo
    """
    params = {'regNo': regNo}
    vehID = db.query(sql, params)
    if len(vehID) == 0:
        sql = """
            WITH
                entID AS (INSERT INTO entities (entity_type) VALUES ('Vehicle') RETURNING entity_id),
                props AS (INSERT INTO properties (entity_id, property_name, property_value, value_type)
                    SELECT entity_id, p.*
                    FROM entID,
                        (VALUES ('Registration No.', :regNo, 'text'), ('Type', :typ, 'text')) AS p(property_name, property_value, value_type))
            SELECT entity_id FROM entID
        """
        params = {'regNo': regNo, 'typ': typ}
        vehID = db.execute(sql, params)[0].entity_id
    else:
        vehID = vehID[0].entity_id

    if st.session_state.vehicleCompany == 'Add New...':
        # Add the company, if not existing
        sql = """
            WITH
                entID AS (INSERT INTO entities (entity_type) VALUES ('Company') RETURNING entity_id),
                props AS (INSERT INTO properties (entity_id, property_name, property_value, value_type)
                    SELECT entity_id, p.* FROM entID,
                        (VALUES ('Name', :cmp, 'text')) AS p(property_name, property_value, value_type))
            SELECT entity_id FROM entID
        """
        params = {'cmp': st.session_state.vehicleCompanyNew}
        cmpID = db.execute(sql, params)[0].entity_id
        _get_companies.clear()
    else:
        cmpID = int(st.session_state.vehicleCompany.split('. ')[0])
    
    # Add the presence of the vehicle
    sql = """
        WITH
            entID AS (INSERT INTO entities (entity_type) VALUES ('Daily Presence') RETURNING entity_id),
            props AS (INSERT INTO properties (entity_id, property_name, property_value, value_type)
                SELECT * FROM entID,
                    (VALUES ('Date', :dat, 'text'),
                        ('Vehicle', :vehID, 'entity_ref'),
                        ('Company', NULL, 'entity_ref'),
                        ('Proxy Company', :cmp, 'entity_ref')) AS p(property_name, property_value, value_type))
        SELECT entity_id from entID
    """
    params = {'dat': st.session_state.selectedDate.isoformat(), 'vehID': str(vehID), 'cmp': str(cmpID)}
    db.execute(sql, params)
    st.session_state.vehicleRegistrationNo = ''
    st.session_state.vehicleTypeNew = ''
    st.session_state.vehicleCompanyNew = ''
    _get_company_and_type_for_vehicle.clear()
    _get_vehicle_types.clear()

def ShowVehicles() -> None:
    if 'vehicleRegistrationNo' in st.session_state and st.session_state.vehicleRegistrationNo != '':
        vehicle_types, companies = _get_company_and_type_for_vehicle(st.session_state.vehicleRegistrationNo)
        vehicle_types = vehicle_types['vehicle_type'].tolist()
        company_names = (companies['company_id'] + '. ' + companies['company_name']).tolist()
        companies_all = _get_companies()
        companies_all_names = (companies_all['company_id'] + '. ' + companies_all['company_name']).tolist()
    else:
        vehicle_types = []
        company_names = []
        companies_all_names = []
    if len(vehicle_types) == 0:
        vehicle_types = _get_vehicle_types()['vehicle_type'].tolist()
    
    st.text_input('Registration No.', label_visibility='visible', key='vehicleRegistrationNo')
    if StreamlitMode.VehicleTypeStandard & st.session_state.Mode:
        st.selectbox('Type', vehicle_types + ['Add New...'], label_visibility='visible', key='vehicleTypeExisting')
        if st.session_state.vehicleTypeExisting == 'Add New...':
            st.session_state.Mode &= ~StreamlitMode.VehicleTypeStandard
            st.session_state.Mode |= StreamlitMode.VehicleTypeNew
            st.rerun()
    elif StreamlitMode.VehicleTypeNew & st.session_state.Mode:
        if st.session_state.vehicleTypeExisting != 'Add New...':
            st.session_state.Mode &= ~StreamlitMode.VehicleTypeNew
            st.session_state.Mode |= StreamlitMode.VehicleTypeStandard
            st.rerun()
        left, right = st.columns([1, 1], vertical_alignment='bottom')
        with left:
            st.selectbox('Type', vehicle_types + ['Add New...'], label_visibility='visible', key='vehicleTypeExisting')
        with right:
            st.text_input('Type', label_visibility='visible', key='vehicleTypeNew')

    if StreamlitMode.VehicleCompaniesStandard & st.session_state.Mode:
        st.selectbox('Company name', company_names + ['Expand...'], label_visibility='visible', key = 'vehicleCompany')
        if st.session_state.vehicleCompany == 'Expand...':
            st.session_state.Mode &= ~StreamlitMode.VehicleCompaniesStandard
            st.session_state.Mode |= StreamlitMode.VehicleCompaniesExpanded
            st.rerun()
    elif StreamlitMode.VehicleCompaniesExpanded & st.session_state.Mode:
        st.selectbox('Company name', companies_all_names + ['Add New...'], label_visibility='visible', key = 'vehicleCompany')
        if st.session_state.vehicleCompany == 'Add New...':
            st.session_state.Mode &= ~StreamlitMode.VehicleCompaniesExpanded
            st.session_state.Mode |= StreamlitMode.VehicleCompaniesNew
            st.rerun()
    elif StreamlitMode.VehicleCompaniesNew & st.session_state.Mode:
        left, right = st.columns([1, 1], vertical_alignment='bottom')
        with left:
            st.selectbox('Company name', companies_all_names + ['Add New...'], label_visibility='visible', key = 'vehicleCompany')
            if st.session_state.vehicleCompany != 'Add New...':
                st.session_state.Mode &= ~StreamlitMode.VehicleCompaniesNew
                st.session_state.Mode |= StreamlitMode.VehicleCompaniesExpanded
        with right:
            st.text_input('Company name', label_visibility='visible', key='vehicleCompanyNew')
    st.button('Add', use_container_width=True, on_click=AddVehicle)

def SetUpStateVariables() -> None:
    if 'Mode' not in st.session_state:
        st.session_state.Mode = StreamlitMode.NameInputStandard | StreamlitMode.VehicleTypeStandard | StreamlitMode.VehicleCompaniesStandard
    if 'Reruns' not in st.session_state:
        st.session_state.Reruns = 0
    if 'PreviousMode' not in st.session_state:
        st.session_state.PreviousMode = st.session_state.Mode
    if 'existingpersonnel' not in st.session_state:
        st.session_state.existingpersonnel = []
    if 'selectedExistingPeople' not in st.session_state:
        st.session_state.selectedExistingPeople = []
    if 'newpersonnel' not in st.session_state:
        st.session_state.newpersonnel = []
    if 'newCompanypersonnel' not in st.session_state:
        st.session_state.newCompanypersonnel = []

def ResetStateVariables() -> None:
    st.session_state.existingpersonnel = []
    st.session_state.selectedExistingPeople = []
    st.session_state.newpersonnel = []
    st.session_state.newCompanypersonnel = []

db = _get_database()
# First, set up all state variable, including modes
SetUpStateVariables()
st.session_state.Reruns += 1
# Secondly, reset state variable, except for modes, if mode changes
if not st.session_state.Mode & st.session_state.PreviousMode:
    ResetStateVariables()
    st.session_state.PreviousMode = st.session_state.Mode
# Plot title
st.title('Presence log')
ShowDate()
people, vehicles, overview = st.tabs(['People', 'Vehicles', 'Overview'])
with people:
    if StreamlitMode.NameInputStandard & st.session_state.Mode:
        ShowCompany()
        if st.session_state.selectedCompany == 'Add New':
            st.session_state.Mode &= ~StreamlitMode.NameInputStandard
            st.session_state.Mode |= StreamlitMode.NameInputNewCompany
            st.rerun()
        ShowExistingpersonnel()
        ShowNewpersonnel()
        st.button('Submit', on_click=SubmitPeople)
    elif StreamlitMode.NameInputNewCompany & st.session_state.Mode:
        ShowCompany()
        if st.session_state.selectedCompany != 'Add New':
            st.session_state.Mode &= ~StreamlitMode.NameInputNewCompany
            st.session_state.Mode |= StreamlitMode.NameInputStandard
            st.rerun()
        ShowNewCompany()
with vehicles:
    ShowVehicles()
with overview:
    ShowAllPeople()
    ShowAllVehicles()
