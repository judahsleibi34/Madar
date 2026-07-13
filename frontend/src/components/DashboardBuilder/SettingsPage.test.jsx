import { describe, expect, it } from "vitest";

import { buildProfilePayload } from "./profilePayload";

describe("SettingsPage canonical email handling", () => {
  it("never includes the displayed canonical email in normal profile updates", () => {
    expect(
      buildProfilePayload({
        first_name: "  Madar ",
        last_name: " Owner  ",
        email: "different@example.com",
        phone: "  +970000000  ",
        avatar: "  /avatar_uploads/test.webp  ",
      })
    ).toEqual({
      first_name: "Madar",
      last_name: "Owner",
      phone: "+970000000",
      avatar: "/avatar_uploads/test.webp",
    });
  });
});
