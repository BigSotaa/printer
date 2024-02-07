import os  
  
from gpt import *  
from video import *  
from utils import *  
from search import *  
from uuid import uuid4  
from tiktokvoice import *  
from flask_cors import CORS  
from termcolor import colored  
from dotenv import load_dotenv  
from flask import Flask, request, jsonify  
from moviepy.config import change_settings  
from apiclient.errors import HttpError    
from youtube import upload_video    
  
# Load environment variables  
load_dotenv("../.env")  
  
# Set environment variables  
SESSION_ID = os.getenv("TIKTOK_SESSION_ID")  
change_settings({"IMAGEMAGICK_BINARY": os.getenv("IMAGEMAGICK_BINARY")})  
  
# Initialize Flask  
app = Flask(__name__)  
CORS(app)  
  
# Constants  
HOST = "0.0.0.0"  
PORT = 8080  
AMOUNT_OF_STOCK_VIDEOS = 5  
GENERATING = False  
  
# Generation Endpoint  
@app.route("/api/generate", methods=["POST"])  
def generate():
    """    Generate a video based on the provided data and optionally upload it to YouTube.

    Returns:
        JSON: A JSON response containing the status of the video generation process and the path to the generated video.

    Raises:
        Exception: An error occurred during the video generation process.
    """
  
    try:  
        # Set global variable  
        global GENERATING  
        GENERATING = True  
  
        # Clean  
        clean_dir("../temp/")  
        clean_dir("../subtitles/")  
  
        # Parse JSON  
        data = request.get_json()  
        
        # Get 'automateYoutubeUpload' from the request data and default to False if not provided 
        automate_youtube_upload = data.get('automateYoutubeUpload', False)  
  
        # Print little information about the video which is to be generated  
        print(colored("[Video to be generated]", "blue"))  
        print(colored("   Subject: " + data["videoSubject"], "blue"))  
  
        if not GENERATING:  
            return jsonify(  
                {  
                    "status": "error",  
                    "message": "Video generation was cancelled.",  
                    "data": [],  
                }  
            )  
  
        # Generate a script  
        script = generate_script(data["videoSubject"])  
  
        # Generate search terms  
        search_terms = get_search_terms(  
            data["videoSubject"], AMOUNT_OF_STOCK_VIDEOS, script  
        )  
  
        # Search for a video of the given search term  
        video_urls = []  
  
        # Loop through all search terms,  
        # and search for a video of the given search term  
        for search_term in search_terms:  
            if not GENERATING:  
                return jsonify(  
                    {  
                        "status": "error",  
                        "message": "Video generation was cancelled.",  
                        "data": [],  
                    }  
                )  
            found_url = search_for_stock_videos(  
                search_term, os.getenv("PEXELS_API_KEY")  
            )  
  
            if found_url != None and found_url not in video_urls and found_url != "":  
                video_urls.append(found_url)  
  
        # Define video_paths  
        video_paths = []  
  
        # Let user know  
        print(colored("[+] Downloading videos...", "blue"))  
  
        # Save the videos  
        for video_url in video_urls:  
            if not GENERATING:  
                return jsonify(  
                    {  
                        "status": "error",  
                        "message": "Video generation was cancelled.",  
                        "data": [],  
                    }  
                )  
            try:  
                saved_video_path = save_video(video_url)  
                video_paths.append(saved_video_path)  
            except Exception:  
                print(colored(f"[-] Could not download video: {video_url}", "red"))  
  
        # Let user know  
        print(colored("[+] Videos downloaded!", "green"))  
  
        # Let user know  
        print(colored("[+] Script generated!\n\n", "green"))  
  
        print(colored(f"\t{script}", "cyan"))  
  
        if not GENERATING:  
            return jsonify(  
                {  
                    "status": "error",  
                    "message": "Video generation was cancelled.",  
                    "data": [],  
                }  
            )  
  
        # Split script into sentences  
        sentences = script.split(". ")  
        # Remove empty strings  
        sentences = list(filter(lambda x: x != "", sentences))  
        paths = []  
        # Generate TTS for every sentence  
        for sentence in sentences:  
            if not GENERATING:  
                return jsonify(  
                    {  
                        "status": "error",  
                        "message": "Video generation was cancelled.",  
                        "data": [],  
                    }  
                )  
            current_tts_path = f"../temp/{uuid4()}.mp3"  
            tts(sentence, "en_us_006", filename=current_tts_path)  
            audio_clip = AudioFileClip(current_tts_path)  
            paths.append(audio_clip)  
  
        # Combine all TTS files using moviepy  
        final_audio = concatenate_audioclips(paths)  
        tts_path = f"../temp/{uuid4()}.mp3"  
        final_audio.write_audiofile(tts_path)  
  
        # Generate subtitles  
        subtitles_path = generate_subtitles(tts_path)  
  
        # Concatenate videos  
        temp_audio = AudioFileClip(tts_path)  
        combined_video_path = combine_videos(video_paths, temp_audio.duration)  
  
        # Put everything together  
        final_video_path = generate_video(combined_video_path, tts_path, subtitles_path)  
          
        if automate_youtube_upload:  # Only proceed with YouTube upload if the toggle is True  
            # Define metadata for the video  
            title, description, keywords = generate_metadata(data["videoSubject"], script)  
  
            # Choose the appropriate category ID for your videos  
            video_category_id = "28"  # Science & Technology  
            privacyStatus = "private"  # "public", "private", "unlisted"  
            video_metadata = {  
                'video_path': os.path.abspath(f"../temp/{final_video_path}"),  
                'title': title,  
                'description': description,  
                'category': video_category_id,  
                'keywords': ",".join(keywords),  
                'privacyStatus': privacyStatus,  
            }  
  
            # Upload the video to YouTube  
            try:  
                # Unpack the video_metadata dictionary into individual arguments  
                video_response = upload_video(  
                    video_path=video_metadata['video_path'],  
                    title=video_metadata['title'],  
                    description=video_metadata['description'],  
                    category=video_metadata['category'],  
                    keywords=video_metadata['keywords'],  
                    privacy_status=video_metadata['privacyStatus']  
                )  
                print(f"Uploaded video ID: {video_response.get('id')}")  
            except HttpError as e:  
                print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")  
        
        # Let user know  
        print(colored(f"[+] Video generated: {final_video_path}!", "green"))  
  
        # Stop FFMPEG processes  
        if os.name == "nt":  
            # Windows  
            os.system("taskkill /f /im ffmpeg.exe")  
        else:  
            # Other OS  
            os.system("pkill -f ffmpeg")  
  
        GENERATING = False  
  
        # Return JSON  
        return jsonify(  
            {  
                "status": "success",  
                "message": "Retrieved stock videos.",  
                "data": final_video_path,  
            }  
        )  
    except Exception as err:  
        print(colored(f"[-] Error: {str(err)}", "red"))  
        return jsonify(  
            {  
                "status": "error",  
                "message": f"Could not retrieve stock videos: {str(err)}",  
                "data": [],  
            }  
        )  
@app.route("/api/cancel", methods=["POST"])  
def cancel():
    """    Cancel the video generation process.

    This function cancels the video generation process and returns a JSON response
    indicating the status and message of the cancellation.

    Returns:
        dict: A dictionary containing the status and message of the cancellation.
    """
  
    print(colored("[!] Received cancellation request...", "yellow"))  
      
    global GENERATING  
    GENERATING = False  
  
    return jsonify({"status": "success", "message": "Cancelled video generation."})  
  
  
if __name__ == "__main__":  
    app.run(debug=True, host=HOST, port=PORT)  