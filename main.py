# Get the length of the ects-fiches of our university site (in order to find empty or almost empty fiches and see which faculty has the longest ects-fiches)
import requests
import re

from bs4 import BeautifulSoup
from tqdm import tqdm
import pickle


# Get a list containing all trajectories of our university site
def get_trajectories():
    # List of all courses https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/?f=23%2C114%2C124
    #  Note: f=124 means only "Academische opleidingen", 114 for "Master" and 23 for bachelor
    html = requests.get(
        'https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/?s=16&lang=nl&f=23%2C114%2C124').text

    parsed_html = BeautifulSoup(html, features="lxml")
    courses_list_html = parsed_html.find(class_="listCourses")
    courses_list_html_objs = courses_list_html.find_all(class_="wrap")

    trajectories = []

    for course in courses_list_html_objs:
        url = course["href"]

        language = "nl" if url.startswith("/nl/") else "en"
        course_slug = url.split("/")[-2]

        # get the degrees (master and/or bachelor)
        degrees_html = course.find_all("div", class_="value")[1]
        degrees_objs = degrees_html.find_all("li")
        degrees = list([degree.text.lower() for degree in degrees_objs])

        trajectories.append({"language": language, "slug": course_slug, "degrees": degrees})

    return trajectories


def get_courses(url):
    # url: study programme url,
    #  e.g. https://www.uantwerpen.be/en/study/programmes/all-programmes/research-master-philosophy/study-programme/

    html = requests.get(url).text
    parsed_html = BeautifulSoup(html, features="lxml")

    course_title_html_obj = parsed_html.find_all("h5")
    courses = []
    for course in course_title_html_obj:
        course_href = course.find("a")["href"]

        course_info = {
            "year": course_href[4:8],
            "id": course_href[9:19],
            "href": course_href,
            "code": course_href[9:13],
            "faculty": course_href[13:16],
            "course": course_href[16:19]
        }

        courses.append(course_info)
    return courses


def fetch_course_info(trajectories):
    all_courses = []
    for trajectory in tqdm(trajectories):
        degrees = trajectory["degrees"]
        slug = trajectory["slug"]
        for degree in degrees:
            if trajectory["language"] == "nl":
                url = f"https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/{slug}/{degree}/studieprogramma/"
            else:
                continue  # Skip english trajectories for now
                # Reason for skip: differenturl formats:
                # https://www.uantwerpen.be/en/study/programmes/all-programmes/epidemiology/about-the-programme/study-programme/
                # https://www.uantwerpen.be/en/study/programmes/all-programmes/research-master-philosophy/study-programme/

            traj_courses = get_courses(url)

            for course in traj_courses:
                if any(course["id"] in c["id"] for c in all_courses):
                    # course already added (probably overlap with another trajectory)
                    continue
                all_courses.append(course)

    with open('all_courses.pickle', 'wb') as f:
        pickle.dump(all_courses, f)

    return all_courses


trajectories = get_trajectories()

# check if all_courses.pickle exists
try:
    with open('all_courses.pickle', 'rb') as f:
        all_courses = pickle.load(f)
except FileNotFoundError:
    all_courses = fetch_course_info(trajectories)
# For each of the courses, request the ects fiche and get the length of the text
try:
    with open('all_courses_extended.pickle', 'rb') as f:
        all_courses = pickle.load(f)
except FileNotFoundError:
    for course in tqdm(all_courses):
        url_params = course["href"]
        html = requests.get(f"https://www.uantwerpen.be/ajax/courseInfo{url_params}").text
        parsed_html = BeautifulSoup(html, features="lxml")

        beautified_course_info = parsed_html.text

        beautified_course_info = re.sub(r'\n+', '\n', beautified_course_info)  # remove double (or more) newlines
        beautified_course_info = re.sub(r'\t', '', beautified_course_info)  # remove tabs
        beautified_course_info = beautified_course_info.replace("\n \n", "\n") # remove lines containing only a space

        course["ects_length"] = len(beautified_course_info)

    with open('all_courses_extended.pickle', 'wb') as f:
        pickle.dump(all_courses, f)

import pandas as pd
import openpyxl as xl

df = pd.DataFrame(all_courses)
df.to_excel("dutch_courses_ects_length.xlsx")

df = df[["faculty", "ects_length"]]
df = df.groupby("faculty").mean()
print(df)