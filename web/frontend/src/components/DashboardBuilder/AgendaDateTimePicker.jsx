import DateTimeInput from "../common/DateTimeInput";

export default function AgendaDateTimePicker({ value, onChange }) {
  return <DateTimeInput id="agenda-task-schedule" type="datetime-local" value={value} onChange={(event) => onChange(event.target.value)} aria-label="Task schedule" pickerLabel="Choose task date and time" />;
}
