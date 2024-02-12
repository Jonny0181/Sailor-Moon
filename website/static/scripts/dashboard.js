const tabs = document.querySelectorAll("nav ul li a");
const tabContents = document.querySelectorAll(".tab-content");

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => {
    // Remove active class from all tabs and tab contents
    tabs.forEach((tab) => tab.classList.remove("active"));
    tabContents.forEach((content) => content.classList.remove("active"));

    // Add active class to the clicked tab and corresponding tab content
    tab.classList.add("active");
    tabContents[index].classList.add("active");
  });
});

const playlistTabs = document.querySelectorAll(
  "#playlist-songs > div > button"
);
const playlistTabContent = document.querySelectorAll(".songs-container .lists");

playlistTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => {
    playlistTabs.forEach((tab) => tab.classList.remove("active"));
    playlistTabContent.forEach((content) => content.classList.remove("active"));

    tab.classList.add("active");
    playlistTabContent[index].classList.add("active");
  });
});

async function currentSongs() {
  populateSongs(currentPlaylist, currentIsCollab);
}

async function playlistRecommendations() {
  console.log(currentPlaylist);
}

// Function to fetch Spotify track information
async function fetchSpotifyTrackInfo(trackUrl) {
  const trackId = trackUrl.split("/").pop();

  const response = await fetch(`https://api.spotify.com/v1/tracks/${trackId}`, {
    headers: {
      Authorization: `Bearer {{spotify_access_token}}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch track info: ${response.status} ${response.statusText}`
    );
  }

  const data = await response.json();
  return data;
}

async function populateUsers(playlistName, isCollaborative) {
  const usersListContainer = document.querySelector(".users-list");
  usersListContainer.innerHTML = "";

  let playlist;
  if (isCollaborative) {
    playlist = collab_data.find(
      (collabPlaylist) => collabPlaylist._id === playlistName
    );
  } else {
    playlist = user_playlists.find(
      (userPlaylist) => userPlaylist.name === playlistName
    );
  }

  if (playlist) {
    const allowedUsers = playlist.allowed_users.filter(
      (userId) => userId !== my_userID
    );

    for (const userId of allowedUsers) {
      try {
        const response = await fetch("/get-user-info", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ user_id: userId }),
        });
        if (!response.ok) {
          throw new Error(
            `Failed to fetch user info: ${response.status} ${response.statusText}`
          );
        }

        let userData = await response.json();
        userData = userData["user_info"];
        const avatarUrl = `https://cdn.discordapp.com/avatars/${userData.id}/${userData.avatar}.png`;
        const userItem = document.createElement("div");
        userItem.innerHTML = `
                          <div class="avatar-name">
                              <img src="${avatarUrl}" alt="User Avatar" />
                              <span>${userData.username}</span>
                          </div>
                          <button class="delete-user" data-userID="${userData.id}" data-playlist="${playlistName}" data-collab="${isCollaborative}">Delete</button>
                      `;
        usersListContainer.appendChild(userItem);
      } catch (error) {
        console.error(`Error fetching user info: ${error}`);
      }
    }
  } else {
    console.error(`Playlist "${playlistName}" not found.`);
  }
}

async function populateSongs(playlistName, isCollaborative) {
  const songsContainer = document.getElementById("songs-list");
  songsContainer.innerHTML = "";

  let playlist;
  if (isCollaborative) {
    playlist = collab_data.find(
      (collabPlaylist) => collabPlaylist._id === playlistName
    );
  } else {
    playlist = user_playlists.find(
      (userPlaylist) => userPlaylist.name === playlistName
    );
  }

  if (playlist) {
    if (playlist.songs.length === 0) {
      const messageContainer = document.createElement("div");
      messageContainer.classList.add("no-songs-message");
      messageContainer.innerHTML = `
                  <h2>Oh no!</h2>
                  <p>Looks like this playlist doesn't have any songs! Add some and come back!</p>
              `;
      songsContainer.appendChild(messageContainer);
    } else {
      for (const trackUrl of playlist.songs) {
        const trackInfo = await fetchSpotifyTrackInfo(trackUrl);

        const songItem = document.createElement("li");
        songItem.classList.add("song-item");

        songItem.innerHTML = `
                      <img src="${
                        trackInfo.album.images[0].url
                      }" alt="Song Thumbnail" class="song-thumbnail" />
                      <div class="song-details">
                          <p class="song-name">${trackInfo.name}</p>
                          <p class="song-artist">${trackInfo.artists
                            .map((artist) => artist.name)
                            .join(", ")}</p>
                      </div>
                      <div class="song-duration">${formatDuration(
                        trackInfo.duration_ms
                      )}</div>
                      <button class="delete-song-button" data-song-url="${trackUrl}" data-is-collaborative="${isCollaborative}">Delete</button>
                  `;

        songsContainer.appendChild(songItem);
      }
    }
  } else {
    console.error(`Playlist "${playlistName}" not found.`);
  }
}

// Function to format track duration
function formatDuration(durationMs) {
  const minutes = Math.floor(durationMs / 60000);
  const seconds = ((durationMs % 60000) / 1000).toFixed(0);
  return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
}

// Add event listener to playlist items to dynamically populate songs
const playlistItems = document.querySelectorAll(".playlists-container li");
playlistItems.forEach((playlistItem) => {
  playlistItem.addEventListener("click", () => {
    // Remove active class from all playlist items
    playlistItems.forEach((item) => item.classList.remove("playlist-active"));

    // Add active class to the clicked playlist item
    playlistItem.classList.add("playlist-active");

    // Determine if the playlist is collaborative
    const isCollaborative = playlistItem.classList.contains("collaborative");

    // Populate songs for the selected playlist
    const playlistId = playlistItem.getAttribute("data-playlist-id");
    currentPlaylist = playlistId;
    currentIsCollab = isCollaborative;
    populateSongs(playlistId, isCollaborative);
    populateUsers(playlistId, isCollaborative);

    // Show or hide the collaborator container based on the playlist type
    const collabContainer = document.getElementById("collab-container");
    collabContainer.style.display = isCollaborative ? "block" : "none";
  });
});

// Add this function to handle song deletion
async function deleteSong(playlistName, songUrl, isCollaborative) {
  try {
    const response = await fetch("/delete-song", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        playlist_name: playlistName,
        song_url: songUrl,
        is_collaborative: isCollaborative,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      user_playlists = data.user_playlists;
      collab_data = data.collab_data;
      return;
    } else {
      console.error(`Failed to delete song: ${data.error}`);
    }
  } catch (error) {
    console.error(`Error during song deletion: ${error}`);
  }
}

async function removeUser(playlist, isCollab, userId) {
  try {
    const response = await fetch("/remove-user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        playlist: playlist,
        userId: userId,
      }),
    });

    const data = await response.json();
    if (response.ok) {
      user_playlists = data.user_playlists;
      collab_data = data.collab_data;
      return populateUsers(currentPlaylist, currentIsCollab);
    } else {
      throw new Error(`Failed to delete user: ${data.error}`);
    }
  } catch (error) {
    console.error(`Error during user deletion: ${error}`);
  }
}

async function addUserToCollabPlaylist() {
  try {
    newUserID = document.getElementById("collab-input").value;
    const response = await fetch("/add-user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        userID: newUserID,
        currentPlaylist: currentPlaylist,
      }),
    });

    const data = await response.json();
    if (response.ok) {
      document.getElementById("collab-input").value = "";
      user_playlists = data.user_playlists;
      collab_data = data.collab_data;
      return populateUsers(currentPlaylist, currentIsCollab);
    }
  } catch (error) {
    console.error(`Error during user adding: ${error}`);
  }
}

async function disconnectSpotify() {
  try {
    const response = await fetch("/spotify-disconnect", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await response.json();
    if (response.ok) {
      return location.reload();
    }
  } catch (error) {
    console.error(`Error during user deletion: ${error}`);
  }
}

document.addEventListener("DOMContentLoaded", function () {
  // Select the first playlist item
  const firstPlaylistItem = document.querySelector(".playlists-container li");
  if (firstPlaylistItem) {
    firstPlaylistItem.click();
  }

  // Add this script to handle delete button click
  document.addEventListener("click", async (event) => {
    if (event.target.classList.contains("delete-song-button")) {
      const playlistItem = document.querySelector(".playlist-active");
      const playlistId = playlistItem.getAttribute("data-playlist-id");
      const songUrl = event.target.getAttribute("data-song-url");
      const isCollaborative =
        event.target.getAttribute("data-is-collaborative") === "true";
      await deleteSong(playlistId, songUrl, isCollaborative);
      event.target.closest(".song-item").remove();
    }
  });

  document.addEventListener("click", async (event) => {
    if (event.target.classList.contains("delete-user")) {
      const userID = event.target.getAttribute("data-userID");
      const playlist = event.target.getAttribute("data-playlist");
      const collab = event.target.getAttribute("data-collab");
      await removeUser(playlist, collab, userID);
    }
  });
});
