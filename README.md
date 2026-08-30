# Medical Clinic Management Web Application

A simple web application for managing an OPD clinic operated by two doctors. It brings patient registration, doctor schedules, appointments, consultations and prescriptions into one system.

The first version is designed for local use.

## Main features

- Secure login for administrators and doctors.
- Patient registration, search and visit history.
- Working schedules and unavailability periods for both doctors.
- Appointment booking, rescheduling and cancellation.
- Prevention of duplicate bookings for the same doctor and time.
- Patient check-in, walk-in registration and a daily OPD queue.
- Consultation notes, diagnoses and treatment plans.
- Prescriptions with medicine instructions and printable output.
- A dashboard showing today's appointments and waiting patients.

## Technology

- Python and FastAPI
- SQLAlchemy for database access
- SQLite for the initial local version
- Jinja templates, HTML, Bootstrap and minimal JavaScript

PostgreSQL and cloud hosting can be introduced later if the clinic needs to support more users or remote access.

## Entity relationship diagram

```mermaid
erDiagram
    USER ||--o| DOCTOR : has_profile
    DOCTOR ||--o{ AVAILABILITY : defines
    DOCTOR ||--o{ DOCTOR_UNAVAILABILITY : blocks
    DOCTOR ||--o{ APPOINTMENT : receives
    PATIENT ||--o{ APPOINTMENT : books
    APPOINTMENT o|--o| VISIT : may_create
    DOCTOR ||--o{ VISIT : conducts
    PATIENT ||--o{ VISIT : attends
    VISIT ||--o| PRESCRIPTION : has
    PRESCRIPTION ||--|{ PRESCRIPTION_ITEM : contains

    USER {
        int id PK
        string username UK
        string password_hash
        string role
        boolean is_active
    }

    DOCTOR {
        int id PK
        int user_id FK, UK
        string display_name
        string registration_number UK
        string phone
        boolean is_active
    }

    PATIENT {
        int id PK
        string medical_record_number UK
        string full_name
        date date_of_birth
        string sex
        string phone
        string address
        string emergency_contact
    }

    AVAILABILITY {
        int id PK
        int doctor_id FK
        int weekday
        time start_time
        time end_time
        int slot_duration_minutes
        boolean is_active
    }

    DOCTOR_UNAVAILABILITY {
        int id PK
        int doctor_id FK
        datetime start_at
        datetime end_at
        string reason
    }

    APPOINTMENT {
        int id PK
        int doctor_id FK
        int patient_id FK
        datetime start_at
        datetime end_at
        string reason
        string status
    }

    VISIT {
        int id PK
        int appointment_id FK
        int doctor_id FK
        int patient_id FK
        int queue_number
        string status
        text presenting_complaint
        text diagnosis
        text clinical_notes
        text treatment_plan
    }

    PRESCRIPTION {
        int id PK
        int visit_id FK, UK
        datetime issued_at
        text general_instructions
    }

    PRESCRIPTION_ITEM {
        int id PK
        int prescription_id FK
        string medicine_name
        string dose
        string frequency
        string duration
        string instructions
    }
```

### How to read the diagram

- `PK` means primary key: the unique identifier of a record.
- `FK` means foreign key: a reference to a record in another entity.
- `UK` means unique key: a value that cannot be repeated.
- `||` means exactly one.
- `o|` means zero or one.
- `o{` means zero or many.
- `|{` means one or many.

### Entities

- **User:** Stores login and access information. A user may have one doctor profile.
- **Doctor:** Stores the professional details of each doctor and connects them to their login account.
- **Patient:** Stores patient identity and contact information. One patient can have many appointments and visits.
- **Availability:** Stores the normal weekdays and hours during which a doctor accepts appointments.
- **Doctor unavailability:** Blocks a specific date or time when a doctor is not available, such as leave.
- **Appointment:** Stores a scheduled booking between a patient and a doctor. Its status shows whether it is scheduled, completed, cancelled or a no-show.
- **Visit:** Represents the patient's actual OPD consultation. It stores the queue number, complaint, diagnosis, clinical notes and treatment plan.
- **Prescription:** Stores the general prescription information for a visit.
- **Prescription item:** Stores each medicine in a prescription, including its dose, frequency, duration and instructions.

### Main relationships

- One doctor can define many availability and unavailability periods.
- One doctor can receive many appointments, but each appointment belongs to one doctor.
- One patient can make many appointments, but each appointment belongs to one patient.
- A scheduled appointment may create one visit when the patient checks in.
- A walk-in patient creates a visit without an appointment. This is why the appointment reference in `VISIT` is optional.
- Every visit belongs to one patient and is conducted by one doctor.
- A visit may have one prescription.
- A prescription must contain one or more prescription items.

### Typical data flow

1. A doctor account and working availability are created.
2. A patient is registered.
3. An appointment is booked using an available doctor and time.
4. When the patient arrives, the appointment creates a visit and a queue number is assigned.
5. The doctor records the consultation and may create a prescription with one or more medicines.

For a walk-in patient, the process starts with a patient record and a visit; no appointment is required.
