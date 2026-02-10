port module App exposing (..)

import Browser exposing (UrlRequest(..))
import Browser.Dom
import Browser.Navigation
import Dict exposing (Dict)
import Html as H exposing (Html)
import Html.Attributes as HA
import Html.Events as HE
import Json.Decode as JD
import Json.Decode.Extra
import Json.Encode as JE
import List.Extra as LE
import NumbasExam exposing 
  ( Exam
  , QuestionPath
  , QuestionSubset
  , Question
  , Part
  , PartInfo
  , NumbasExamError
  , rewrite_part_path
  )
import GroupPartPath exposing (GroupPartPath)
import PartPath exposing (PartPath)
import Set exposing (Set)
import Task
import Tuple exposing (pair, first, second)
import Url exposing (Url)
import Url.Builder as UB
import Url.Parser as UP exposing ((</>))
import Url.Parser.Query as UPQ
import Util exposing (indexedConcatMap)

raw_html : List (String,String) -> String -> Html msg
raw_html attributes content = H.node "raw-html" ((List.map (\(k,v) -> HA.attribute k v) attributes)++[HA.attribute "content" content]) []

imported_html : ImportedHTML -> Html msg
imported_html = raw_html []

icon name = raw_html [("style", "display: inline")] <| """<svg alt="" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 180 180"><use href="/static/icons.svg#"""++name++""""></use></svg>"""

port save_tags : JE.Value -> Cmd msg

gatherByKey : (a -> comparable) -> List a -> List (comparable, List a)
gatherByKey key = LE.gatherEqualsBy key >> List.map (\(a,rest) -> (key a, a::rest))

pluralise n single plural = case n of
  1 -> single
  _ -> plural

jam = Json.Decode.Extra.andMap

ff = String.fromFloat
fi = String.fromInt
nocmd model = (model, Cmd.none)

main = Browser.application
    { init = init
    , update = update
    , subscriptions = subscriptions
    , view = view
    , onUrlRequest = onUrlRequest
    , onUrlChange = onUrlChange
    }

type alias User =
  { pk : Int
  , first_name : String
  , last_name : String
  }

full_name : User -> String
full_name user = user.first_name++" "++user.last_name

type alias Attempt =
  { pk : Int
  , user : User
  , question_subsets: QuestionSubset
  , question_scores : Dict Int QuestionScore
  , interactions : Dict String Interaction
  , source : JD.Value
  }

type alias QuestionScore =
  { raw_score : Float
  , max_score : Float
  , completion_status : String
  }

type alias Interaction =
  { raw_score : Float
  , max_score : Float
  , learner_response : String
  , correct_answer: String
  }

get_interaction : String -> Attempt -> Maybe Interaction
get_interaction path = .interactions >> Dict.get path

blank_interaction : Interaction
blank_interaction =
  { raw_score = -1
  , max_score = -1
  , learner_response = ""
  , correct_answer = ""
  }

type alias AnswerInfo =
  { answer : String
  , attempts : List (Attempt, Interaction)
  , tags : Set String
  , editing_tag : String
  }

type alias ExamData = 
  { exam : Exam
  , attempts : List Attempt
  , part_answers : Dict String (List AnswerInfo)
  , filter_tags : Set String
  , show_attempts : Dict String Bool
  }

type LoadingError
  = LoadingExamError NumbasExamError
  | LoadingAttemptsError JD.Error
  | LoadingTagsError JD.Error

type DataModel
  = FailedLoading LoadingError
  | LoadedExam ExamData

maybe_data : DataModel -> Maybe ExamData
maybe_data md = case md of
  LoadedExam data -> Just data
  _ -> Nothing

type alias ImportedHTML = String

type alias Model = 
  { data : DataModel
  , view : View
  , nav_key : Browser.Navigation.Key
  , run_attempt_url : String
  , footer_html : ImportedHTML
  , top_nav_html : ImportedHTML
  }

type View
  = Overview
  | ViewQuestion QuestionPath
  | ViewPart GroupPartPath

type Msg
  = SetView View
  | PushView View
  | SetTag String String String
  | AddTag String String
  | SwapTag String String String
  | SetShowAttempts String Bool
  | ToggleFilterTag String String Bool
  | NoOp
  | GoExternal String

parse_question_ref : String -> Maybe QuestionPath
parse_question_ref =
  String.split "q"
  >> List.filterMap String.toInt
  >> (\l -> case l of
      a::b::[] -> Just (a,b)
      _ -> Nothing
     )

question_ref_tostring : QuestionPath -> String
question_ref_tostring (gn,qn) = (fi gn)++"q"++(fi qn)

view_from_url : Url -> Maybe View
view_from_url =
  let
    query = 
      UPQ.map2 
        (\mq mp -> case (mq, mp) of
          (_, Just path) -> ViewPart path
          (Just qref, _) -> ViewQuestion qref
          _ -> Overview
        )
        (UPQ.string "question" |> UPQ.map (Maybe.andThen parse_question_ref))
        (UPQ.string "part" |> UPQ.map (Maybe.andThen GroupPartPath.fromString))
      |> UP.query

  in
    (UP.oneOf
      [ query
      , UP.s "resource"
        </>
        UP.int
        </>
        UP.s "analysis"
        </>
        query
       |> UP.map (\_ v -> v)
      ]
     |> UP.parse
    )

type alias Flags =
  { exam_source : String
  , data : JE.Value
  , run_attempt_url : String
  , footer_html : ImportedHTML
  , top_nav_html : ImportedHTML
  }

type alias SavedTags = Dict String (Dict String (List String))

init : Flags -> Url -> Browser.Navigation.Key -> (Model, Cmd msg)
init flags url nav_key = 
  let
    nview : View
    nview = view_from_url url |> Maybe.withDefault Overview

    q = JD.decodeValue (JD.dict JD.value) flags.data

    rexam = 
       NumbasExam.fromString flags.exam_source
       |> Result.mapError LoadingExamError

    rattempts = 
       JD.decodeValue (JD.field "attempts" decode_attempt_dump) flags.data
       |> Result.mapError LoadingAttemptsError

    rtags = 
       JD.decodeValue (JD.field "tags" decode_tags) flags.data
       |> Result.mapError LoadingTagsError

    data = 
      Result.map3
        (\exam attempts tags ->
          let
            parts : List (GroupPartPath, PartInfo)
            parts = NumbasExam.all_parts exam

            attempt_interactions : List (Attempt, List (GroupPartPath, Interaction))
            attempt_interactions =
              attempts
              |> List.map (\attempt -> 
                  ( attempt
                  , attempt.interactions
                    |> Dict.toList
                    |> List.filterMap (\(spath,int) -> PartPath.fromString spath |> Maybe.map (\path -> (path,int)))
                    |> List.map (Tuple.mapFirst (rewrite_part_path attempt.question_subsets exam))
                  )
                )


            part_attempts : GroupPartPath -> List (Attempt, Interaction)
            part_attempts path =
                 attempt_interactions
              |> List.filterMap (\(a,interactions) -> LE.find (first >> (==) path) interactions |> Maybe.map (\(_,int) -> (a,int)) )
              |> List.filter (\(a,int) -> int.learner_response /= "")
            
            part_incorrect_answers : GroupPartPath -> List AnswerInfo
            part_incorrect_answers path =
              part_attempts path
              |> List.filter (\(a,int) -> int.raw_score == 0)
              |> gatherByKey (second >> .learner_response)
              |> List.sortBy (second >> List.length)
              |> List.reverse
              |> List.map (\(answer, atts) -> 
                  { answer = answer
                  , attempts = atts
                  , tags = Set.empty
                  , editing_tag = ""
                  }
                 )
    
            path_answer_tags : List (String, Dict String (Set String))
            path_answer_tags =
                 tags
              |> Dict.toList
              |> List.map (Tuple.mapSecond (Dict.map (\_ -> Set.fromList)))
  
            part_answers =
              parts
              |> List.map (\(path,part) -> 
                    (GroupPartPath.toString path, part_incorrect_answers path)
                 )
              |> Dict.fromList
              |> (\pa ->
                  List.foldl
                    (\(path, answers) ->
                      Dict.update path (Maybe.map (List.map (\a -> { a | tags = Set.union a.tags (Dict.get a.answer answers |> Maybe.withDefault Set.empty)})))
                    )
                    pa
                    path_answer_tags
                 )
          in
            LoadedExam
              { exam = exam
              , attempts = attempts
              , part_answers = part_answers
              , filter_tags = Set.empty
              , show_attempts = Dict.empty
              }
        )
        rexam
        rattempts
        rtags
      |> \r -> case r of
        Ok d -> d
        Err err -> FailedLoading err

    model : Model
    model =
      { data = data
      , view = nview
      , nav_key = nav_key
      , run_attempt_url = flags.run_attempt_url
      , footer_html = flags.footer_html
      , top_nav_html = flags.top_nav_html
      }

    decode_tags : JD.Decoder SavedTags
    decode_tags = (JD.dict (JD.dict (JD.list JD.string)))

  in
    model |> nocmd

get_part : String -> Attempt -> Maybe Interaction
get_part path = .interactions >> Dict.get path 

update_part : String -> (Interaction -> Interaction) -> Attempt -> Attempt
update_part path fn attempt = 
  {attempt | interactions = Dict.update path (Maybe.andThen (fn >> Just)) attempt.interactions }

update_data : (ExamData -> ExamData) -> Model -> Model
update_data updater model = case model.data of
  LoadedExam data -> { model | data = LoadedExam (updater data) }
  _ -> model

update_answerinfo : (AnswerInfo -> AnswerInfo) -> String -> String -> Model -> Model
update_answerinfo updater path answer model =
  case model.data of
    LoadedExam data ->
      let
        npart_answers = 
          data.part_answers
          |> Dict.update 
            path
            (Maybe.map (LE.updateIf (.answer >> (==) answer) updater))
            
        ndata = LoadedExam { data | part_answers = npart_answers }
      in
        { model | data = ndata }

    _ -> model

id_for_answer : String -> String -> Model -> String
id_for_answer path answer model = 
  model.data
  |> maybe_data
  |> Maybe.andThen (.part_answers >> Dict.get path)
  |> Maybe.andThen (LE.findIndex (.answer >> (==) answer))
  |> Maybe.map (\ai -> path++"-answer-"++(fi ai))
  |> Maybe.withDefault ""

url_for_view : View -> String
url_for_view nview =
  let
    query = case nview of
      Overview -> []
      ViewQuestion qref -> [UB.string "question" (question_ref_tostring qref)]
      ViewPart path -> [UB.string "part" (GroupPartPath.toString path)]
  in
    if query == [] then "?" else UB.toQuery query 

cmd_save_tags : Model -> (Model, Cmd Msg)
cmd_save_tags model = 
  case model.data of
    LoadedExam data ->
      (model, save_tags <| encode_part_answerinfo data)
    
    _ ->
      (model, Cmd.none)

update msg model = case msg of
  SetView nview -> { model | view = nview } |> nocmd

  PushView nview -> 
    ( { model | view = nview } 
    , Browser.Navigation.pushUrl model.nav_key (url_for_view nview)
    )

  AddTag path answer -> 
    update_answerinfo 
      (\a -> { a | tags = if a.editing_tag == "" then a.tags else Set.insert a.editing_tag a.tags, editing_tag = "" })
      path
      answer
      model
    |> cmd_save_tags

  SetTag path answer tag -> 
    update_answerinfo
      (\a -> { a | editing_tag = tag })
      path
      answer
      model
    |> nocmd

  SwapTag path answer tag -> 
    (update_answerinfo
      (\a -> { a | editing_tag = tag, tags = Set.filter ((/=) tag) a.tags |> if a.editing_tag /= "" then Set.insert a.editing_tag else identity } )
      path
      answer
      model
        
    , Task.attempt (\_ -> NoOp) (Browser.Dom.focus <| (id_for_answer path answer model)++"-tag")
    )

  SetShowAttempts spath show -> model |> update_data (\m -> {m | show_attempts = Dict.insert spath show m.show_attempts }) |> nocmd

  ToggleFilterTag path tag filtered ->
    update_data
      (\data ->
        let 
          filter_tags = (if filtered then Set.insert else Set.remove) tag data.filter_tags
        in
          { data | filter_tags = filter_tags }
      )
      model
    |> nocmd

  NoOp -> model |> nocmd

  GoExternal url -> (model, Browser.Navigation.load url)

apply_first : List (a -> Maybe (b -> b)) -> a -> b -> b
apply_first handlers thing bb =
  List.foldl 
    (\handler (going,b) -> 
      if not going then 
        (going, b)
      else 
        case handler thing of
          Just fn -> (False, fn b)
          Nothing -> (True, b)
    )
    (True, bb)
    handlers
  |> second

subscriptions model = Sub.none

decode_attempt_dump : JD.Decoder (List Attempt)
decode_attempt_dump = JD.list decode_attempt

decode_attempt : JD.Decoder Attempt
decode_attempt =
  JD.succeed Attempt
  |> jam (JD.field "pk" JD.int)
  |> jam (JD.field "user" decode_user)
  |> jam (JD.field "questionSubsets" (JD.list (JD.list JD.int)))
  |> jam (JD.field "scores" (JD.list decode_question_score |> JD.map Dict.fromList))
  |> jam (JD.field "interactions" decode_interactions)
  |> jam (JD.value)

decode_user : JD.Decoder User
decode_user =
  JD.succeed User
  |> jam (JD.field "pk" JD.int)
  |> jam (JD.field "first_name" JD.string)
  |> jam (JD.field "last_name" JD.string)

decode_question_score : JD.Decoder (Int,QuestionScore)
decode_question_score = 
  JD.map2 pair
    (JD.field "number" JD.int)
    ( JD.succeed QuestionScore
      |> jam (JD.field "raw_score" JD.float)
      |> jam (JD.field "max_score" JD.float)
      |> jam (JD.field "completion_status" JD.string)
    )

decode_str_float : JD.Decoder Float
decode_str_float =
  JD.string
  |> JD.andThen (\s -> case String.toFloat s of
    Nothing -> JD.fail "expected a float"
    Just n -> JD.succeed n
  )

decode_interactions : JD.Decoder (Dict String Interaction)
decode_interactions =
  JD.dict (JD.succeed Interaction
    |> jam (JD.field "1" decode_str_float ) -- max_score
    |> jam (JD.field "0" decode_str_float ) -- raw_score
    |> jam (JD.field "2" JD.string) -- learner_response
    |> jam (JD.field "3" JD.string) -- correct_response
  )

review_attempt_link : Model -> Attempt -> Html Msg
review_attempt_link model attempt = 
  H.a
    [ HA.href <| String.replace "12345" (fi attempt.pk) model.run_attempt_url
    , HA.target "review"
    ]
    [ H.text <| full_name attempt.user
    ]



view_part_info : Bool -> ExamData -> Model -> GroupPartPath -> PartInfo -> Html Msg
view_part_info show_prompt examdata model path part =
  let
    prompt_part = case path of
      (_,(_,_,Nothing)) -> part
      (gn,(qn,pn,Just _)) -> 
        examdata.exam
        |> NumbasExam.get_part (gn,(qn,pn,Nothing))
        |> Maybe.map .info
        |> Maybe.withDefault part
  
    prompt = 
      JD.decodeValue (JD.field "prompt" JD.string) prompt_part.source
      |> Result.withDefault ""

    spath = GroupPartPath.toString path

    show_attempts = Dict.get spath examdata.show_attempts |> Maybe.withDefault False
  
    answers : List AnswerInfo
    answers = Dict.get spath examdata.part_answers |> Maybe.withDefault []
    
    all_tags : Set String
    all_tags =
         answers
      |> List.foldl (\a s -> Set.union s a.tags) Set.empty

    tag_frequencies = 
      answers 
      |> List.concatMap (.tags >> Set.toList) 
      |> LE.frequencies
      |> List.sortBy second
      |> List.reverse

    correctAnswer = case part.type_ of
      "numberentry" ->
        JD.decodeValue 
          (JD.map2 (\min max -> H.span [] [H.text "between ", H.code [] [H.text min], H.text " and ", H.code [] [H.text max]])
            (JD.field "minValue" JD.string)
            (JD.field "maxValue" JD.string)
          )
          part.source
        |> Result.withDefault (H.text "")

      _ ->
        JD.decodeValue
          (JD.field "answer" JD.string
           |> JD.map (\ans -> H.code [] [H.text ans])
          )
          part.source
        |> Result.withDefault (H.text "")

    pattempts : List AnswerInfo
    pattempts = 
         Dict.get spath examdata.part_answers 
      |> Maybe.withDefault []
      |> List.filter 
          (\ainfo -> 
            examdata.filter_tags == Set.empty 
            || (Set.intersect ainfo.tags examdata.filter_tags /= Set.empty)
          )

    format_answer : String -> String
    format_answer pattern = case part.type_ of
      "numberentry" -> case String.split "[:]" pattern of
        [min,max] -> if min==max then min else pattern
        _ -> pattern

      "jme" -> String.dropLeft (String.indices "}" pattern |> List.head |> Maybe.withDefault -1 |> (+) 1) pattern
      
      _ -> pattern

    answers_table = case pattempts of
      [] -> H.p [] [H.text "Nobody got this wrong."]
      _ -> 
        H.details
          (if show_prompt then [ HA.attribute "open" "" ] else [])
          [ H.summary [] [H.text <| fi <| List.length pattempts, H.text " incorrect answers"]
          , H.p
            []
            [ H.input 
                [ HA.id <| spath++"-show-attempts" 
                , HA.type_ "checkbox"
                , HA.class "inline"
                , HA.checked show_attempts
                , HE.onCheck (SetShowAttempts spath)
                ]
                []
            , H.label
                [ HA.for <| spath++"-show-attempts"
                ]
                [ H.text "Show individual attempts" ]
            ]
          , H.table 
            [ HA.class "incorrect-answers"
            , HA.classList
                [("show-attempts", show_attempts)
                ]
            ] 
            [ H.colgroup
                []
                [ H.col [HA.class "answer"] []
                , H.col [HA.class <| if show_attempts then "name" else "frequency"] []
                , H.col [HA.class "expected-answer"] []
                , H.col [HA.class "tags"] []
                ]
            , H.thead
                []
                [H.tr 
                  [] 
                  ([ H.th [] [H.text "Answer"]
                  , H.th [] [H.text <| if show_attempts then "Name" else "Frequency"]
                  ]++(if show_attempts then [H.th [] [H.text "Expected answer"]] else [])
                  ++
                  [ H.th [] [H.text "Tags"]
                  ]
                  )
                ]
            , H.tbody
                []
                (pattempts |> List.indexedMap
                  (\ai ainfo ->
                    let
                      answer = ainfo.answer

                      atts = ainfo.attempts

                      editing_tag = ainfo.editing_tag

                      atags = ainfo.tags |> Set.toList
                    in
                      atts
                      |> (if show_attempts then identity else List.take 1)
                      |> List.indexedMap (\atti (a,int) ->
                        H.tr 
                          [ HA.classList [("new-answer", atti==0)] ] 
                          (( if atti==0 then 
                              [ H.td
                                [ HA.class "answer"
                                , HA.rowspan <| if not show_attempts then 1 else List.length atts ]
                                [ H.code [] [H.text answer] ]
                              ]
                            else
                              []
                          )++
                          (if show_attempts then
                              [ H.td
                                [ HA.class "name" ]
                                [ review_attempt_link model a
                                ]
                              , H.td
                                [ HA.class "expected-answer" ]
                                [H.code [] [H.text <| format_answer int.correct_answer]
                                ]
                              ]
                            else
                              [ H.td
                                [ HA.class "frequency" ]
                                [ H.text <| fi <| List.length atts ]
                              ]
                          )++
                          ( if atti==0 then
                            [ H.td
                              [ HA.class "tags"
                              , HA.rowspan <| if not show_attempts then 1 else List.length atts ]
                              [ H.form
                                [ HE.preventDefaultOn "submit" (JD.succeed <| (AddTag spath answer, True))
                                , HA.class "tags-form"
                                ]
                                [ H.ul
                                   [ HA.class "assigned-tags" ]
                                   (   atags
                                    |> List.map (\tag -> 
                                        H.li 
                                          []
                                          [ H.button
                                            [ HE.onClick (SwapTag spath answer tag)
                                            , HA.class "tag info"
                                            , HA.type_ "button"
                                            ]
                                            [ H.text tag ]
                                          ]
                                       )
                                   )
                                , H.input 
                                  [ HA.value editing_tag
                                  , HE.onInput (SetTag spath answer)
                                  , HE.on "change" (JD.succeed <| AddTag spath answer)
                                  , HA.list <| spath++"-tags"
                                  , HA.id <| (id_for_answer spath answer model)++"-tag"
                                  ]
                                  []
                                ]
                              ]
                            ]
                            else
                              []
                          )
                        )
                      )
                    ) 
                  |> List.concatMap identity
                )
            ]
          ]

    label = NumbasExam.short_part_label path

    type_name = 
      Dict.get part.type_ NumbasExam.part_type_names
      |> Maybe.withDefault part.type_

    (num_done, num_answers) = part_todo examdata path
    finished_tagging = num_done == num_answers
  in
    H.article
      [ HA.class "part-info" ] 
      [ H.h3 
        [] 
        [ H.a [HA.href <| url_for_view (ViewPart path)] [H.text <| label ]
        , H.text " "
        , H.span [HA.class "type muted"] [H.text type_name]
        , H.text " "
        , if num_answers > 0 then
            H.span 
              [ HA.classList 
                [ ("status",True)
                , ("pill", True)
                , ("success", finished_tagging)
                , ("warning", not finished_tagging)
                ]
              ]
              [H.text <| (fi num_done)++"/"++(fi num_answers)++" answers tagged"]
          else
            H.text ""
        ]
      , if show_prompt then
          H.blockquote [ HA.class "prompt alert" ] [raw_html [] prompt]
        else
          H.text ""
      , if part.type_ == "gapfill" then H.text "" else H.p [] [H.text "Correct answer: ", correctAnswer]
      , if tag_frequencies == [] then H.text "" else
        H.table
          [ HA.class "tag-frequency" ]
          [ H.thead
            []
            [ H.tr [] [H.th [] [H.text "Tag" ], H.th [] [H.text "Frequency"]] ]
          , H.tbody
            []
            (tag_frequencies |> List.map (\(tag,n) -> 
              let
                filtered = Set.member tag examdata.filter_tags
              in
                H.tr 
                [] 
                [ H.td 
                  [] 
                  [ H.label 
                    [ HA.class "tag button" ] 
                    [ H.text tag 
                    , H.input
                      [ HA.type_ "checkbox"
                      , HA.class "inline"
                      , HA.checked filtered
                      , HE.onCheck (ToggleFilterTag spath tag)
                      ]
                      []
                    ]
                  ]
                , H.td [] [H.text <| fi n]
                ]
            ))
          ]
      , if part.type_ == "gapfill" then H.text "" else answers_table
      , H.datalist
          [ HA.id <| spath++"-tags" ]
          (tags_across_exam examdata |> List.map (first >> \tag -> H.option [ HA.value tag ] []))
      ]


view_part : ExamData -> Model -> GroupPartPath -> Part -> Html Msg
view_part examdata model ((gn,(qn,pn,mgn)) as path) part =
  let
    gaps = case part.gaps of
      [] -> H.text ""
      
      _ -> 
        H.ul 
          [ HA.class "gaps" ] 
          (List.indexedMap (\gapn gap -> H.li [] [view_part_info False examdata model (gn,(qn,pn,Just gapn)) gap]) part.gaps)
  in
    H.article
      []
      [ view_part_info True examdata model path part.info
      , gaps
      ]
      
view_question : ExamData -> Model -> QuestionPath -> Question -> Html Msg
view_question examdata model ((gn,qn) as qref) question =
  let
    attempts = examdata.attempts

    exam = examdata.exam

    current_group = LE.getAt gn exam.question_groups

    statement = JD.decodeValue (JD.field "statement" JD.string) question.source

    prev_qref : Maybe QuestionPath
    prev_qref = 
      if qn == 0 then 
        LE.getAt (gn-1) exam.question_groups
        |> Maybe.map (\g -> (gn-1,(List.length g)-1))
      else
        Just (gn,qn-1)

    pair_question : Maybe QuestionPath -> Maybe (QuestionPath, Question)
    pair_question = Maybe.andThen (\mqref -> Maybe.map (pair mqref) (NumbasExam.get_question mqref exam))
    
    next_qref : Maybe QuestionPath
    next_qref = 
      let
        group_size = LE.getAt gn exam.question_groups |> Maybe.map List.length |> Maybe.withDefault 0
      in
        if qn >= group_size-1 then 
          Just (gn+1, 0)
        else
          Just (gn, qn+1)

    prev_question = pair_question prev_qref
    
    next_question = pair_question next_qref
    
    things =  
        question.parts
        |> List.indexedMap (\pn part ->
          [(gn,(qn,pn,Nothing))]
          ++(List.indexedMap (\gapn gap -> (gn,(qn,pn,Just gapn))) part.gaps)
          )
        |> List.concatMap identity
    
    pass = things |> List.map (\path -> part_todo examdata path |> \(a,b) -> a > 0 || b == 0)

    question_pager =
      pager
        "question"
        (prev_question |> Maybe.map (first >> ViewQuestion))
        (next_question |> Maybe.map (first >> ViewQuestion))
        (breadcrumbs
          [ (ViewQuestion qref, question_label qref question)
          ]
          model
        )
  in
    H.main_
      [] 
      [ question_pager
      , H.article
        []
        [ H.h2 [] [H.text <| question_label qref question]
        , case statement of
            Ok s -> H.blockquote [HA.class "statement alert"] [raw_html [] s]
            Err _ -> H.text ""
        , H.ul [ HA.class "parts" ] (List.indexedMap (\pn part -> H.li [] [view_part examdata model (gn,(qn,pn,Nothing)) part]) question.parts)
        ]
      ]

question_label : QuestionPath -> Question -> String
question_label (gn,qn) question = "G"++(fi <| gn + 1)++"Q"++(fi <| qn + 1)++": "++question.name

view : Model -> Browser.Document Msg
view model = 
  {
    title = "Numbas attempt analysis",
    body = 
      [imported_html model.top_nav_html
      ]
      ++ (case model.data of
          FailedLoading error -> 
            [ H.main_
              []
              [ H.p [] [H.text "There was an error loading the data."]
              , H.pre [] [H.text <|case error of
                  LoadingExamError exam_error -> "Error loading the exam: "++NumbasExam.errorToString exam_error
                  LoadingAttemptsError attempts_error -> "Error loading the attempts data: "++(JD.errorToString attempts_error)
                  LoadingTagsError tags_error -> "Error loading the tags data: "++(JD.errorToString tags_error)
                ]
              ]
            ]
            
          LoadedExam data -> view_with_exam data model
      ) ++ [ imported_html model.footer_html ]
  }

tags_across_exam : ExamData -> List (String, (List (String, String)))
tags_across_exam data =
  data.part_answers
  |> Dict.toList
  |> List.concatMap (\(path, answers) -> 
      answers |> List.concatMap (\a -> a.tags |> Set.toList |> List.map (\tag -> (path, a.answer, tag)))
     )
  |> List.sortBy (\(path,answer,tag) -> tag)
  |> LE.groupWhile (\(_,_,t1) (_,_,t2) -> t1==t2)
  |> List.map (\((p1,a1,tag), others) -> (tag,(p1,a1)::(List.map (\(p,a,_) -> (p,a)) others)))
  |> List.sortBy (second >> List.length)
  |> List.reverse


assess_todo : (a -> List b) -> (b -> Bool) -> a -> (Int, Int)
assess_todo getter checker thing =
  let
    things = getter thing

    nthings = List.length things

    passed = List.filter checker things
  in
    (List.length passed, nthings)


part_todo : ExamData -> GroupPartPath -> (Int, Int)
part_todo data = 
  assess_todo 
  ( \path -> Dict.get (GroupPartPath.toString path) data.part_answers
    |> Maybe.withDefault []
  )
  (.tags >> (/=) Set.empty)


question_todo : ExamData -> (QuestionPath, Question) -> (Int, Int)
question_todo data =
  assess_todo
    (\((gn,qn),q) -> 
        q.parts
        |> List.indexedMap (\pn part ->
          [(gn,(qn,pn,Nothing))]
          ++(List.indexedMap (\gapn gap -> (gn,(qn,pn,Just gapn))) part.gaps)
          )
        |> List.concatMap identity
        |> List.filter (\path -> Dict.get (GroupPartPath.toString path) data.part_answers |> Maybe.withDefault [] |> (/=) [])
    )
    (\path -> part_todo data path |> \(a,b) -> a == b)


breadcrumbs : List (View, String) -> Model -> Html Msg
breadcrumbs crumbs model =
  H.ul
    [ HA.id "breadcrumbs" ]
    (List.map (\(v,label) -> 
      H.li 
        [] 
        [ H.a 
          ( [HA.href <| url_for_view v] 
          ++ (if model.view == v then [HA.attribute "aria-current" "step"] else [])
          )
          [H.text label]
        ]
      )
      crumbs
    )

pager : String -> Maybe View -> Maybe View -> Html Msg -> Html Msg
pager item_name prev_item next_item middle = 
  H.nav 
    [ HA.class "pager" ]
    [ case prev_item of
      Nothing -> H.text <| "This is the first "++item_name++"."
      Just pv -> 
        H.a 
          [ HA.href <| url_for_view <| pv
          , HA.rel "prev"
          , HA.class "prev button"
          ]
          [icon "arrow-left", H.text <| " Previous "++item_name]
    , middle
    , case next_item of
      Nothing -> H.text <| "This is the last "++item_name++"."
      Just nv -> 
        H.a 
          [ HA.href <| url_for_view <| nv
          , HA.rel "next"
          , HA.class "next button"
          ]
          [H.text <| "Next "++item_name++" ", icon "arrow-right"]
    ]


view_with_exam : ExamData -> Model -> List (Html Msg)
view_with_exam data model =
  let
    exam = data.exam

    header = 
      H.header
        []
        [ H.h1 [] [H.a [HA.href <| url_for_view Overview] [H.text <| "Analysis of attempts at "++exam.name]]
        ]
    
    page_structure : Html Msg -> List (Html Msg)
    page_structure content =
      [ header 
      , content
      ]

    overview _ = 
      let
        all_tags = tags_across_exam data
      in
        [ header
        , H.main_
          []
          [ H.p [] [H.text "On this page you can examine the incorrect answers given for each question part, and tag them to identify common mistakes." ]
          , H.section
            []
            [ H.table
              [ HA.id "toc" ]
              [ H.caption [] [H.text "Questions" ]
              , H.thead
                []
                [H.tr [] [H.th [] [H.text "Question"], H.th [] [H.text "Status"]]]
              , H.tbody
                []
                (exam.question_groups |> indexedConcatMap (\gn questions ->
                  (  [ H.tr [] [H.th [HA.colspan 2] [H.text <| "Group "++(fi gn)]]]
                   ++(questions |> List.indexedMap (\qn q ->
                      let
                        qref = (gn,qn)

                        (num_done,num_parts) = question_todo data (qref,q)

                        done = num_done == num_parts
                      in
                        H.tr 
                          []
                          [ H.td
                            []
                            [ H.a [HA.href <| url_for_view <| ViewQuestion qref] [ H.text <| q.name] ]
                          , H.td
                            [ HA.classList [("success",done)]]
                            [ H.text <| " " ++ (fi num_done)++"/"++(fi num_parts)++" tagged" ]
                          ]
                     ))
                  )
                ))
              ]
            ]
          , H.section
            []
            [ H.h2 [] [H.text "Tags"]
            , H.p
              []
              [ H.a
                  [ HA.href "analysis/tags"
                  , HA.class "button info"
                  ]
                  [ icon "save"
                  , H.text " Download tag data as JSON"
                  ]
              ]
            , H.table
              [ HA.id "global-tags" ]
              [ H.caption
                []
                [ H.text "Tags used across the exam" ]
              , H.thead
                []
                [ H.tr [] [H.th [] [H.text "Tag" ], H.th [] [H.text "Uses"]]
                ]
              , H.tbody
                []
                (all_tags |> List.map (\(tag, uses) ->
                  H.tr
                    []
                    [ H.td [] [H.span [HA.class "tag" ] [H.text <| tag] ]
                    , H.td [] 
                      [ H.details
                        []
                        [ H.summary [] [H.text <| (List.length uses |> fi)++" "++(pluralise (List.length uses) "use" "uses")]
                        , H.ul
                          []
                          (uses |> LE.gatherEqualsBy first |> List.filterMap (\((path,a1),answers) -> 
                            GroupPartPath.fromString path
                            |> Maybe.map (\ppath -> 
                            
                                H.li 
                                  [] 
                                  [H.a [ HA.href <| url_for_view <| ViewPart <| ppath ] [H.text <| NumbasExam.part_label exam ppath]
                                  , H.text <| " ×"++(fi <| (List.length answers) + 1)
                                  ]
                               )
                          ))
                        ]
                      ]
                    ]
                ))
              ]
            ]
          ]
        ]

    question_view qref = case NumbasExam.get_question qref exam of
      Nothing -> [ H.text "Bad question???" ]
      Just q -> 
          page_structure
            (view_question data model qref q)

    part_view : GroupPartPath -> List (Html Msg)
    part_view ((gn,(qn,pn,mgapn)) as path) = 
      let
        mquestion = NumbasExam.get_question (gn,qn) exam

        mpart = NumbasExam.get_part path exam

        label = PartPath.label (second path)

        pp = NumbasExam.prev_part path exam

        np = NumbasExam.next_part path exam

      in
        Maybe.map2 (\question part -> 
          let
            part_pager = pager 
              "part"
              (Maybe.map ViewPart pp)
              (Maybe.map ViewPart np)
              (breadcrumbs
                ([(ViewQuestion (gn,qn), question_label (gn,qn) question)
                 ]++(case mgapn of
                  Nothing -> [ (ViewPart path, label) ]
                  Just gapn -> 
                    let
                      ppath = (gn,(qn,pn,Nothing))
                    in
                      [ (ViewPart ppath, PartPath.label (second ppath))
                      , (ViewPart path, label)
                      ]
                ))
                model
              )

          in
            page_structure
              (H.main_
                []
                [ part_pager
                , H.article
                  []
                  [ view_part data model path part ]
                , part_pager
                ]
              )
        )
          mquestion
          mpart
        |> Maybe.withDefault [H.text <| "Bad part?? "++(GroupPartPath.toString path)]
  in
    case model.view of
      Overview -> overview ()
      ViewQuestion qn -> question_view qn
      ViewPart path -> part_view path

onUrlRequest req =
  case req of
    Internal url -> case view_from_url url of
        Just nview -> PushView nview
        Nothing -> GoExternal <| Url.toString url
    External url -> GoExternal url

onUrlChange = 
  view_from_url
  >> Maybe.map SetView
  >> Maybe.withDefault NoOp

encode_part_answerinfo : ExamData -> JE.Value
encode_part_answerinfo =
  .part_answers
  >> (Dict.filter (\_ -> List.filter (.tags >> (/=) Set.empty) >> (/=) []))
  >> JE.dict identity (\answers -> 
      JE.object
        ( answers
        |> List.filter (.tags >> (/=) Set.empty)
        |> List.map (\ainfo -> (ainfo.answer, JE.list JE.string (ainfo.tags |> Set.toList)))
        )
     )
