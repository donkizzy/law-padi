let navigations = 0

/** Counts committed router navigations; preloads don't count. */
export const recordNavigation = () => {
  navigations += 1
}

/** True only while the router resolves the page the visitor landed on. */
export const isLandingNavigation = () => navigations <= 1
