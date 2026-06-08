import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BriefingReaderPage from "@/app/briefings/[id]/page";
import { createWrapper } from "../helpers/query-wrapper";
import { makeBriefingDetail } from "../helpers/fixtures";
import type { BriefingDetail } from "@/lib/types";

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
  useParams: vi.fn(() => ({ id: "42" })),
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

const mockFetch = vi.hoisted(() => vi.fn<(url: string) => Promise<Response>>());
vi.stubGlobal("fetch", mockFetch);

function mockJsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

describe("BriefingReaderPage", () => {
  const briefing = makeBriefingDetail({
    id: 42,
    content_html:
      "<h2>Your Daily Briefing</h2><p>The Fed held rates steady.</p>",
    content_text: "Your Daily Briefing\nThe Fed held rates steady.",
  });

  beforeEach(() => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/users/5/briefings/42")) {
        return Promise.resolve(mockJsonResponse(briefing));
      }
      return Promise.resolve(mockJsonResponse({}, 404));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    expect(screen.getByTestId("reader-loading")).toBeInTheDocument();
  });

  it("renders briefing reader after load", async () => {
    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("briefing-reader")).toBeInTheDocument();
    });
  });

  it("renders reader header", async () => {
    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("reader-header")).toBeInTheDocument();
    });
  });

  it("renders HTML content via HTMLRenderer", async () => {
    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("html-renderer")).toBeInTheDocument();
    });
    expect(screen.getByTestId("html-renderer").innerHTML).toContain(
      "Your Daily Briefing",
    );
  });

  it("renders back link to /briefings", async () => {
    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("back-link")).toBeInTheDocument();
    });
    expect(screen.getByTestId("back-link")).toHaveAttribute(
      "href",
      "/briefings",
    );
  });

  it("shows error state on 404", async () => {
    mockFetch.mockResolvedValue(mockJsonResponse({}, 404));

    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("reader-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Briefing not found")).toBeInTheDocument();
  });

  it("falls back to plain text when content_html is empty", async () => {
    const textOnly = makeBriefingDetail({
      id: 42,
      content_html: "",
      content_text: "Plain text briefing content here",
    });
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/users/5/briefings/42")) {
        return Promise.resolve(mockJsonResponse(textOnly));
      }
      return Promise.resolve(mockJsonResponse({}, 404));
    });

    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("plaintext-renderer")).toBeInTheDocument();
    });
    expect(screen.getByTestId("plaintext-renderer")).toHaveTextContent(
      "Plain text briefing content here",
    );
  });

  it("shows no-content message when both html and text are empty", async () => {
    const empty = makeBriefingDetail({
      id: 42,
      content_html: "",
      content_text: "",
    });
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/users/5/briefings/42")) {
        return Promise.resolve(mockJsonResponse(empty));
      }
      return Promise.resolve(mockJsonResponse({}, 404));
    });

    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("no-content")).toBeInTheDocument();
    });
    expect(screen.getByTestId("no-content")).toHaveTextContent(
      "This briefing has no content",
    );
  });

  it("shows story count badge", async () => {
    render(<BriefingReaderPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("story-count-badge")).toBeInTheDocument();
    });
  });
});
