"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ApiError, getVideoResult } from "../../../lib/api";
import type { VideoResultResponse } from "../../../lib/types";

interface VideoResultPageProps {
  params: {
    videoId: string;
  };
}

const SPOTIFY_PLAYLIST_URL_REGEX = /https?:\/\/open\.spotify\.com\/playlist\/([a-zA-Z0-9]+)[^\s]*/gi;

function extractSpotifyPlaylistUrl(response: VideoResultResponse): string | null {
  const textBuckets: string[] = [];
  for (const item of response.items) {
    textBuckets.push(item.title);
    textBuckets.push(item.description);
    textBuckets.push(...item.tags);
  }

  for (const bucket of textBuckets) {
    SPOTIFY_PLAYLIST_URL_REGEX.lastIndex = 0;
    const match = SPOTIFY_PLAYLIST_URL_REGEX.exec(bucket);
    if (match?.[1]) {
      return `https://open.spotify.com/playlist/${match[1]}`;
    }
  }

  return null;
}

function toSpotifyEmbedUrl(playlistUrl: string): string {
  const parsed = new URL(playlistUrl);
  const segments = parsed.pathname.split("/").filter(Boolean);
  const playlistId = segments.at(-1);
  return `https://open.spotify.com/embed/playlist/${playlistId}?utm_source=generator`;
}

export default function VideoResultPage({ params }: VideoResultPageProps) {
  const [data, setData] = useState<VideoResultResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async (): Promise<void> => {
      setIsLoading(true);
      try {
        const response = await getVideoResult(params.videoId);
        if (!active) {
          return;
        }
        setData(response);
        setError(null);
      } catch (err: unknown) {
        if (!active) {
          return;
        }
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Failed to load parsed result.");
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, [params.videoId]);

  const spotifyPlaylistUrl = useMemo(() => {
    if (!data) {
      return null;
    }
    return extractSpotifyPlaylistUrl(data);
  }, [data]);

  const spotifyEmbedUrl = useMemo(() => {
    if (!spotifyPlaylistUrl) {
      return null;
    }
    try {
      return toSpotifyEmbedUrl(spotifyPlaylistUrl);
    } catch {
      return null;
    }
  }, [spotifyPlaylistUrl]);

  return (
    <section className="card hero">
      <span className="eyebrow">Result</span>
      <h1 className="title">Video {params.videoId}</h1>
      <p className="lead">Structured output extracted from the completed pipeline.</p>

      {isLoading ? <p className="feedback">Loading parsed content...</p> : null}
      {error ? <p className="feedback feedback-error">{error}</p> : null}

      {data ? (
        <>
          {data.items.length === 0 ? (
            <p className="feedback feedback-warning">
              No parsed items were found for this video yet.
            </p>
          ) : (
            <div className="results-grid">
              {data.items.map((item, index) => (
                <article className="result-item" key={`${item.title}-${index}`}>
                  <h3>{item.title || `Result item ${index + 1}`}</h3>
                  <p>{item.description || "No description available."}</p>
                  {item.tags?.length ? (
                    <div className="tag-row">
                      {item.tags.map((tag) => (
                        <span className="tag" key={tag}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}

          <section className="playlist-card">
            <h3>Spotify Playlist</h3>
            {spotifyPlaylistUrl ? (
              <>
                <p className="lead">
                  Playlist data was detected in extracted content. Open externally or preview below.
                </p>
                <div className="actions">
                  <Link
                    className="button button-primary"
                    href={spotifyPlaylistUrl}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    Open in Spotify
                  </Link>
                </div>
                {spotifyEmbedUrl ? (
                  <iframe
                    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
                    className="playlist-frame"
                    loading="lazy"
                    src={spotifyEmbedUrl}
                    title="Spotify playlist preview"
                  />
                ) : null}
              </>
            ) : (
              <p className="feedback feedback-warning">
                No Spotify playlist URL was found in the current result payload.
              </p>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}
