import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import StoryDetailPage from "@/app/stories/[id]/page";
import { createWrapper } from "../helpers/query-wrapper";
import {
  makeStoryDetail,
  makeResonance,
  makeSource,
  makeEngagement,
} from "../helpers/fixtures";
import type { StoryDetail, Resonance, Source, Engagement } from "@/lib/types";

const mockSession = vi.hoisted(() =>
  vi.fn(() => ({
    data: {
      user: { id: 5, email: "user@test.com", name: "Test User" },
    },
    status: "authenticated",
  })),
);

vi.mock("next-auth/react", () => ({
  useSession: mockSession,
}));

vi.mock("next/navigation", () => ({
  useParams: vi.fn(() => ({ id: "1" })),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

type FetchResponse = StoryDetail | Resonance | Source[] | Engagement;

const mockFetch = vi.hoisted(() => vi.fn<(url: string) => Promise<Response>>());

vi.stubGlobal("fetch", mockFetch);

function mockApiResponse(url: string, data: FetchResponse, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

describe("StoryDetailPage", () => {
  const story = makeStoryDetail({ id: 1 });
  const resonance = makeResonance({ cluster_id: 1 });
  const sources = [
    makeSource({ id: 1, name: "Reuters" }),
    makeSource({ id: 2, name: "AP News" }),
  ];

  beforeEach(() => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/stories/1/resonance")) {
        return Promise.resolve(mockApiResponse(url, resonance));
      }
      if (url.includes("/stories/1")) {
        return Promise.resolve(mockApiResponse(url, story));
      }
      if (url.includes("/sources")) {
        return Promise.resolve(mockApiResponse(url, sources));
      }
      if (url.includes("/engagements")) {
        return Promise.resolve(
          mockApiResponse(url, makeEngagement(), 201),
        );
      }
      return Promise.resolve(mockApiResponse(url, {} as FetchResponse, 404));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    expect(screen.getByTestId("story-loading")).toBeInTheDocument();
  });

  it("renders story headline after load", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("story-detail")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      story.headline,
    );
  });

  it("renders neutral summary", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(story.summary)).toBeInTheDocument();
    });
  });

  it("renders resonance panel after load", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("resonance-panel")).toBeInTheDocument();
    });
    expect(screen.getByText("4.72")).toBeInTheDocument();
  });

  it("renders perspectives", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(
        screen.getAllByTestId("perspective-card").length,
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders article sources list", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("article-list")).toBeInTheDocument();
    });
  });

  it("renders engagement bar", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("engagement-bar")).toBeInTheDocument();
    });
  });

  it("records open engagement on mount", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      const engagementCalls = mockFetch.mock.calls.filter(
        ([url]) => typeof url === "string" && url.includes("/engagements"),
      );
      expect(engagementCalls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error state when story fetch fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/stories/1") && !url.includes("resonance")) {
        return Promise.resolve(mockApiResponse(url, {} as FetchResponse, 404));
      }
      if (url.includes("/sources")) {
        return Promise.resolve(mockApiResponse(url, sources));
      }
      return Promise.resolve(mockApiResponse(url, {} as FetchResponse, 404));
    });

    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("story-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Story not found")).toBeInTheDocument();
  });

  it("fires save engagement on Save button click", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("engagement-bar")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("save-btn"));

    await waitFor(() => {
      const engagementCalls = mockFetch.mock.calls.filter(
        ([url]) => typeof url === "string" && url.includes("/engagements"),
      );
      // At least 2: one "open" on mount + one "save"
      expect(engagementCalls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("fires skip engagement on Skip button click", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("engagement-bar")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("skip-btn"));

    await waitFor(() => {
      const engagementCalls = mockFetch.mock.calls.filter(
        ([url]) => typeof url === "string" && url.includes("/engagements"),
      );
      expect(engagementCalls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("renders breadcrumb navigation", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
    expect(screen.getByText("Dashboard")).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("renders quality indicator", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("quality-indicator")).toBeInTheDocument();
    });
  });

  it("records read on unmount when no explicit engagement", async () => {
    const realDateNow = Date.now;
    const startTime = realDateNow();

    let callCount = 0;
    vi.spyOn(Date, "now").mockImplementation(() => {
      callCount++;
      return callCount <= 2 ? startTime : startTime + 5000;
    });

    const { unmount } = render(<StoryDetailPage />, {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(screen.getByTestId("story-detail")).toBeInTheDocument();
    });

    const callsBefore = mockFetch.mock.calls.length;
    unmount();

    await waitFor(() => {
      const newCalls = mockFetch.mock.calls.slice(callsBefore);
      const readCalls = newCalls.filter(
        ([url, init]) =>
          typeof url === "string" &&
          url.includes("/engagements") &&
          init &&
          typeof init === "object" &&
          "body" in init &&
          typeof init.body === "string" &&
          init.body.includes('"read"'),
      );
      expect(readCalls.length).toBeGreaterThanOrEqual(1);
    });

    vi.spyOn(Date, "now").mockRestore();
  });

  it("does not record read on unmount after save", async () => {
    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("engagement-bar")).toBeInTheDocument();
    });

    // Click save (marks engagedExplicitly)
    fireEvent.click(screen.getByTestId("save-btn"));
    await waitFor(() => {
      const engagementCalls = mockFetch.mock.calls.filter(
        ([url]) => typeof url === "string" && url.includes("/engagements"),
      );
      expect(engagementCalls.length).toBeGreaterThanOrEqual(2);
    });

    const callsBefore = mockFetch.mock.calls.length;

    // Advance time then unmount
    const startTime = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(startTime + 10000);
    const { unmount } = render(<StoryDetailPage />, {
      wrapper: createWrapper(),
    });
    unmount();

    // No new "read" engagement should fire
    const newCalls = mockFetch.mock.calls.slice(callsBefore);
    const readCalls = newCalls.filter(
      ([url, init]) =>
        typeof url === "string" &&
        url.includes("/engagements") &&
        init &&
        typeof init === "object" &&
        "body" in init &&
        typeof init.body === "string" &&
        init.body.includes('"read"'),
    );
    expect(readCalls).toHaveLength(0);

    vi.spyOn(Date, "now").mockRestore();
  });

  it("handles unauthenticated user (no open engagement)", async () => {
    mockSession.mockReturnValue({
      data: null,
      status: "unauthenticated",
    });

    render(<StoryDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("story-detail")).toBeInTheDocument();
    });

    // No engagement calls should be made without userId
    const engagementCalls = mockFetch.mock.calls.filter(
      ([url]) => typeof url === "string" && url.includes("/engagements"),
    );
    expect(engagementCalls).toHaveLength(0);

    // Restore
    mockSession.mockReturnValue({
      data: {
        user: { id: 5, email: "user@test.com", name: "Test User" },
      },
      status: "authenticated",
    });
  });
});
