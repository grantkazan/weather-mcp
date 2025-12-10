from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server

import os

mcp = FastMCP(
    "weather",
    host="0.0.0.0",  # Bind to all interfaces for Railway
    port=int(os.environ.get("PORT", 8000))  # Use Railway's assigned port
)

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
    	latitude: Latitude of the location (recommended: up to 4 decimal places)
    	longitude: Longitude of the location (recommended: up to 4 decimal places)
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


# end weather logic

# hospital logic

@mcp.tool()
async def get_doctors() -> str:
    """Get list of available doctors at the hospital.
    
    Returns information about doctors including their names and specialties.
    """
    url = "https://telnyx-assignment-production.up.railway.app/doctors"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            doctors = response.json()
            
            if not doctors:
                return "No doctors found in the system."
            
            # Format the doctors list
            doctor_list = []
            for doctor in doctors:
                doctor_info = f"Dr. {doctor['name']} - Specialty: {doctor['specialty']}"
                doctor_list.append(doctor_info)
            
            return "Available doctors:\n" + "\n".join(doctor_list)
            
        except Exception as e:
            return f"Unable to fetch doctor information: {str(e)}"

# add remaining logic once they've been tested locally


@mcp.tool()
async def get_appointments(patient_phone: str = None) -> str:
    """Get appointments, optionally filtered by patient phone number.
    
    Args:
        patient_phone: Optional phone number to filter appointments (format: 1-555-0101)
    """
    url = "https://telnyx-assignment-production.up.railway.app/appointments"
    if patient_phone:
        url += f"?patient_phone={patient_phone}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            appointments = response.json()
            
            if not appointments:
                return "No appointments found."
            
            # Format appointments
            appt_list = []
            for appt in appointments:
                if 'doctor_name' in appt:
                    appt_info = f"Appointment ID {appt['id']}: {appt['doctor_name']} on {appt['datetime']} - Status: {appt['status']}"
                else:
                    appt_info = f"Appointment ID {appt['id']} on {appt['datetime']} - Status: {appt['status']}"
                appt_list.append(appt_info)
            
            return "Appointments:\n" + "\n".join(appt_list)
            
        except Exception as e:
            return f"Unable to fetch appointments: {str(e)}"

@mcp.tool()
async def check_availability(doctor_name: str, date: str) -> str:
    """Check available appointment slots for a doctor on a specific date.
    
    Args:
        doctor_name: Name of the doctor (e.g., 'Dr. Smith', 'Smith', 'Dr. Jones')
        date: Date to check in YYYY-MM-DD format (e.g., 2025-12-11)
    """
    # First, get the doctor ID
    async with httpx.AsyncClient() as client:
        doctors_response = await client.get("https://telnyx-assignment-production.up.railway.app/doctors", timeout=30.0)
        doctors = doctors_response.json()
        
        # Find matching doctor
        doctor_id = None
        for doctor in doctors:
            if doctor_name.lower() in doctor['name'].lower():
                doctor_id = doctor['id']
                break
        
        if not doctor_id:
            return f"Doctor '{doctor_name}' not found. Available doctors: {', '.join([d['name'] for d in doctors])}"
        
        # Now check availability
        url = f"https://telnyx-assignment-production.up.railway.app/appointments/available?doctor_id={doctor_id}&date={date}"
        
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            slots = data.get('available_slots', [])
            if not slots:
                return f"No available slots for {doctor_name} on {date}."
            
            return f"Available slots for {doctor_name} on {date}:\n" + "\n".join(slots)
            
        except Exception as e:
            return f"Unable to check availability: {str(e)}"

@mcp.tool() # book patient appointment
async def book_appointment(doctor_name: str, patient_phone: str, patient_name: str, appointment_datetime: str) -> str:
    """Book a new appointment for a patient.
    
    Args:
        doctor_name: Name of the doctor (e.g., 'Dr. Smith', 'Smith')
        patient_phone: Patient's phone number (format: 1-555-0101)
        patient_name: Patient's full name
        appointment_datetime: Appointment datetime in YYYY-MM-DD HH:MM:SS format (e.g., 2025-12-11 14:00:00)
    """
    async with httpx.AsyncClient() as client:
        # First, get the doctor ID
        doctors_response = await client.get("https://telnyx-assignment-production.up.railway.app/doctors", timeout=30.0)
        doctors = doctors_response.json()
        
        doctor_id = None
        for doctor in doctors:
            if doctor_name.lower() in doctor['name'].lower():
                doctor_id = doctor['id']
                break
        
        if not doctor_id:
            return f"Doctor '{doctor_name}' not found. Available doctors: {', '.join([d['name'] for d in doctors])}"
        
        # Book the appointment
        url = "https://telnyx-assignment-production.up.railway.app/appointments"
        payload = {
            "doctor_id": doctor_id,
            "patient_phone": patient_phone,
            "patient_name": patient_name,
            "datetime": appointment_datetime
        }
        
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            
            return f"Appointment booked successfully! Appointment ID: {result['appointment_id']} - {patient_name} with {doctor_name} on {appointment_datetime}"
            
        except httpx.HTTPStatusError as e:
            return f"Failed to book appointment: {e.response.text}"
        except Exception as e:
            return f"Unable to book appointment: {str(e)}"

@mcp.tool() # reschedule an appointment. NEEDS APPT ID - change later?
async def reschedule_appointment(appointment_id: int, new_datetime: str) -> str:
    """Reschedule an existing appointment to a new time.
    
    Args:
        appointment_id: ID of the appointment to reschedule
        new_datetime: New datetime in YYYY-MM-DD HH:MM:SS format (e.g., 2025-12-11 15:00:00)
    """
    url = f"https://telnyx-assignment-production.up.railway.app/appointments/{appointment_id}"
    payload = {"datetime": new_datetime}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(url, json=payload, timeout=30.0)
            response.raise_for_status()
            
            return f"Appointment {appointment_id} successfully rescheduled to {new_datetime}"
            
        except Exception as e:
            return f"Unable to reschedule appointment: {str(e)}"

@mcp.tool()
async def cancel_appointment(appointment_id: int) -> str:
    """Cancel an existing appointment.
    
    Args:
        appointment_id: ID of the appointment to cancel
    """
    url = f"https://telnyx-assignment-production.up.railway.app/appointments/{appointment_id}"
    payload = {"status": "cancelled"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(url, json=payload, timeout=30.0)
            response.raise_for_status()
            
            return f"Appointment {appointment_id} cancelled successfully"
            
        except Exception as e:
            return f"Unable to cancel appointment: {str(e)}"



# end rest of local MCP methods

def main():
    mcp.run(transport='streamable-http', mount_path='/mcp')

if __name__ == "__main__":
    main()