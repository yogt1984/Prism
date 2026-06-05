import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardLayout from "@/components/dashboard/DashboardLayout";

vi.mock("next-auth/react", () => ({
  useSession: () => ({
    data: { user: { name: "Alice", email: "alice@example.com" } },
  }),
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("DashboardLayout", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
  });

  it("renders children in main content area", () => {
    renderWithQuery(
      <DashboardLayout>
        <div data-testid="child">Hello</div>
      </DashboardLayout>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("renders sidebar", () => {
    renderWithQuery(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>,
    );
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });

  it("passes trigger props to sidebar", () => {
    const onTrigger = vi.fn();
    renderWithQuery(
      <DashboardLayout
        onTriggerBriefing={onTrigger}
        isTriggerPending={true}
      >
        <div>Content</div>
      </DashboardLayout>,
    );
    expect(screen.getByText("Generating...")).toBeInTheDocument();
  });

  it("uses flex layout", () => {
    const { container } = renderWithQuery(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>,
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex");
  });
});
