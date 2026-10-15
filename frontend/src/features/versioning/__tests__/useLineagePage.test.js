import { describe, expect, it } from "vitest";
import { artifactsFromProjects } from "../useLineagePage";

describe("artifactsFromProjects", () => {
  const projects = [
    {
      id: "1",
      files: [
        { id: 10, schema_name: "proj_a", display_name: "Raw A", file_type: "raw_data" },
        { id: 11, schema_name: "proj_cb", display_name: "Codes", file_type: "codebook" },
      ],
    },
    {
      id: "2",
      files: [
        { id: 11, schema_name: "proj_cb", display_name: "Codes", file_type: "codebook" },
        { id: 12, schema_name: "proj_c", display_name: "Coding", file_type: "coding" },
      ],
    },
  ];

  it("dedupes files shared across projects and labels their type", () => {
    const items = artifactsFromProjects(projects, "");
    expect(items.map((item) => item.id)).toEqual(["proj_a", "proj_cb", "proj_c"]);
    expect(items[1].description).toBe("Codebook");
  });

  it("narrows to one project", () => {
    const items = artifactsFromProjects(projects, "2");
    expect(items.map((item) => item.id)).toEqual(["proj_cb", "proj_c"]);
  });
});
