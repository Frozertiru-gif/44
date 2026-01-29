export type TrackEvent = {
  name: string;
  payload?: Record<string, string | number | boolean | undefined>;
};

export const track = (event: TrackEvent): void => {
  if (process.env.NODE_ENV === "development") {
    console.info("[track]", event.name, event.payload ?? {});
  }
};
