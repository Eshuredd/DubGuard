import React from "react";
import { registerRoot, Composition } from "remotion";
import { Film } from "./video";
registerRoot(() => (
  <Composition
    id="DubGuard"
    component={Film}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={6450}
  />
));
