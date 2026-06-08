import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BriefingsListPage from "@/app/briefings/page";
import { createWrapper } from "../helpers/query-wrapper";
import { makeBriefing, makeBriefingDetail } from "../helpers/fixtures";
import type { Briefing, BriefingDetail } from "@/lib/types";

const mockPush = vi.fn();

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
  useRouter: () => ({ push: mockPush }),
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

const mockFetch = vi.hoisted(() => vi.fn<(url: string, init?: RequestInit) => Promise<Response>>());
vi.stubGlobal("fetch", mockFetch);

function mockJsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

function makeBriefingList(count: number = 20): Briefing[] {
  return Array.from({ length: count }, (_, i) =>
    makeBriefing({
      id: 100 - i,
      story_count: 10 - (i % 5),
      sent: i % 3 !== 0,
      created_at: new Date(
        Date.now() - i * 86_400_000,
      ).toISOString(),
    }),
  );
}

describe("BriefingsListPage", () => {
  beforeEach(() => {
    localStorage.clear();
    mockPush.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<BriefingsListPage />, { wrapper: createWrapper() });
    expect(screen.getByTestId("briefings-loading")).toBeInTheDocument();
  });

  it("renders briefing list after load", async () => {
    const briefings = makeBriefingList(5);
    mockFetch.mockResolvedValue(mockJsonResponse(briefings));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("briefings-list")).toBeInTheDocument();
    });
    expect(screen.getAllByTestId("briefing-list-item")).toHaveLength(5);
  });

  it("shows empty state when no briefings", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse([]));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("briefings-empty")).toBeInTheDocument();
    });
    expect(screen.getByText("No briefings yet")).toBeInTheDocument();
    expect(
      screen.getByText("Your first one arrives at 7am UTC"),
    ).toBeInTheDocument();
  });

  it("shows error state when fetch fails", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse({}, 500));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("briefings-error")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Could not load briefings"),
    ).toBeInTheDocument();
  });

  it("renders heading", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(makeBriefingList(3)));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Your Briefings")).toBeInTheDocument();
    });
  });

  it("renders trigger briefing button", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(makeBriefingList(3)));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(
        screen.getByTestId("trigger-briefing-btn"),
      ).toBeInTheDocument();
    });
  });

  it("renders pagination", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(makeBriefingList(20)));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("pagination")).toBeInTheDocument();
    });
  });

  it("renders trigger button in empty state", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse([]));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(
        screen.getByTestId("trigger-briefing-btn"),
      ).toBeInTheDocument();
    });
  });

  it("disables Previous on first page", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(makeBriefingList(20)));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("pagination-prev")).toBeDisabled();
    });
  });

  it("enables Next when full page returned", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(makeBriefingList(20)));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("pagination-next")).not.toBeDisabled();
    });
  });

  it("disables Next when partial page returned", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse(makeBriefingList(5)));

    render(<BriefingsListPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("pagination-next")).toBeDisabled();
    });
  });
});
