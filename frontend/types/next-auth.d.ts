import "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: number;
      email: string;
      name?: string | null;
      image?: string | null;
      isPro: boolean;
      interests: string;
    };
  }
}
