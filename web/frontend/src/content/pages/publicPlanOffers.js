// Owner-approved public USD starting prices. Presentation only: these offers
// never create quotes, select billing price books, or grant paid capabilities.
export const publicPlanOffers = {
  currency: "USD",
  modules: [
    { id: "forms", startingMinor: 1500 },
    { id: "website", startingMinor: 2000 },
    { id: "ecommerce", startingMinor: 2000 },
    { id: "statistics", startingMinor: 3000 },
    { id: "elearning", startingMinor: 3000 },
  ],
  allModulesMinor: 10000,
};
