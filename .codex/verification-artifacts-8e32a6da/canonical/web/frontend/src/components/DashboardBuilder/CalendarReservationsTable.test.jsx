import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CalendarReservationsTable from "./CalendarReservationsTable";
import { listBuilderReservations } from "../PageBuilder/services/PageBuilder.api";

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  listBuilderReservations: vi.fn(),
}));

const reservation = {
  id: "reservation-1",
  project_id: "project-1",
  site_subdomain: "palcode",
  reservation_title: "AI coaching session",
  customer_name: "Maya Hassan",
  customer_email: "maya@example.com",
  customer_phone: "+970590000000",
  starts_at: "2026-08-22T09:00:00+03:00",
  ends_at: "2026-08-22T09:30:00+03:00",
  timezone: "Asia/Jerusalem",
  status: "confirmed",
  created_at: "2026-08-21T10:00:00Z",
  updated_at: "2026-08-21T10:15:00Z",
  payload: {
    customAnswers: { goals: ["Prompting", "Automation"] },
    service: "Private lesson",
  },
  field_snapshot: [{
    reservation: {
      formItems: [{ id: "goals", type: "checkbox", label: "What do you want to learn?" }],
    },
  }],
};

describe("CalendarReservationsTable", () => {
  afterEach(cleanup);

  beforeEach(() => {
    listBuilderReservations.mockReset();
    listBuilderReservations.mockResolvedValue({
      reservations: [reservation],
      pagination: { has_more: false },
    });
  });

  it("shows structured reservation records without a separate details action", async () => {
    render(<CalendarReservationsTable />);

    expect(await screen.findByText("Maya Hassan")).toBeTruthy();
    const table = screen.getByRole("table");
    expect(within(table).getByText("maya@example.com")).toBeTruthy();
    expect(within(table).getByText("+970590000000")).toBeTruthy();
    expect(within(table).getByText("AI coaching session")).toBeTruthy();
    expect(within(table).getByText("confirmed")).toBeTruthy();

    expect(within(table).getAllByRole("columnheader")).toHaveLength(6);
    expect(screen.queryByRole("button", { name: /All details/i })).toBeNull();
  });

  it("filters reservations by search and status", async () => {
    render(<CalendarReservationsTable />);
    await screen.findByText("Maya Hassan");

    fireEvent.change(screen.getByLabelText("Search reservations"), { target: { value: "missing" } });
    expect(screen.getByText("No reservations found")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Search reservations"), { target: { value: "maya" } });
    fireEvent.change(screen.getByLabelText("Filter reservations by status"), { target: { value: "confirmed" } });
    expect(screen.getByText("Maya Hassan")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Filter reservations by status"), { target: { value: "cancelled" } });
    expect(screen.getByText("No reservations found")).toBeTruthy();
  });

  it("continues loading while the API reports another page", async () => {
    listBuilderReservations
      .mockResolvedValueOnce({ reservations: [reservation], pagination: { has_more: true } })
      .mockResolvedValueOnce({ reservations: [{ ...reservation, id: "reservation-2", customer_name: "Omar" }], pagination: { has_more: false } });

    render(<CalendarReservationsTable />);
    expect(await screen.findByText("Omar")).toBeTruthy();
    await waitFor(() => expect(listBuilderReservations).toHaveBeenCalledTimes(2));
    expect(listBuilderReservations).toHaveBeenNthCalledWith(2, { limit: 100, offset: 1 });
  });
});
